"""
SaaS seeding utilities — S0-006

Provides idempotent conversion of legacy ProductBundle seed data into the new
Package / PackageVersion / Entitlement catalog.
"""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from app.core.module.registry import MODULE_REGISTRY
from app.core.saas.models import (
    Package,
    PackageVersion,
    PackageVersionAvailability,
    PackageVersionAvailabilityStatus,
    PackageVersionEntitlement,
    PackageVersionLimit,
    PackageVersionPricing,
)
from app.extensions import db
from utils.db_safety import safe_commit


class SeedError(Exception):
    """Raised when seeding cannot proceed."""


def seed_packages_from_product_bundles(
    *,
    created_package_ids: list[int] | None = None,
) -> list[int]:
    """Idempotently create Package/PackageVersion records from ProductBundle seeds.

    For each active ProductBundle that does not already have a Package with the
    same slug, creates:
      - Package
      - PackageVersion (version 1.0.0)
      - PackageVersionPricing (monthly + yearly)
      - PackageVersionLimit (users, patients, storage, api_calls)
      - PackageVersionEntitlement (one per module capability)
      - PackageVersionAvailability (available)

    Returns the list of created Package IDs.
    """
    from app.core.tenant.models import ProductBundle

    created_ids: list[int] = []
    bundles = db.session.execute(select(ProductBundle).filter_by(is_active=True)).scalars().all()

    for bundle in bundles:
        existing = db.session.execute(select(Package).filter_by(slug=bundle.slug)).scalars().first()
        if existing:
            if created_package_ids is not None:
                created_package_ids.append(existing.id)
            # A bundle edited after the package was first created used to
            # leave the package selling the old module set. The entitlements
            # now follow the bundle.
            sync_package_entitlements_for_bundle(bundle, existing)
            continue

        package = Package(
            name=bundle.name,
            name_ar=bundle.name_ar or bundle.name,
            slug=bundle.slug,
            category=_category_for_bundle(bundle),
            is_active=bundle.is_active and bundle.is_public,
        )
        db.session.add(package)
        db.session.flush()

        version = PackageVersion(
            package_id=package.id,
            version='1.0.0',
            changelog='Migrated from ProductBundle seed',
            trial_days=0,
            grace_days=0,
            published_at=datetime.now(UTC),
        )
        db.session.add(version)
        db.session.flush()

        # Pricing
        db.session.add(
            PackageVersionPricing(
                package_version_id=version.id,
                billing_type='monthly',
                price=bundle.monthly_price or Decimal(0),
                setup_fee=bundle.setup_fee or Decimal(0),
                currency=bundle.currency or 'SAR',
            )
        )
        db.session.add(
            PackageVersionPricing(
                package_version_id=version.id,
                billing_type='yearly',
                price=bundle.yearly_price or Decimal(0),
                setup_fee=bundle.setup_fee or Decimal(0),
                currency=bundle.currency or 'SAR',
            )
        )

        # Limits
        limit_map = {
            'max_users': bundle.max_users,
            'max_patients': bundle.max_patients,
            'storage_gb': bundle.storage_gb,
            'api_calls_per_month': bundle.api_calls_per_month,
        }
        for key, value in limit_map.items():
            if value is None:
                continue
            db.session.add(
                PackageVersionLimit(
                    package_version_id=version.id,
                    limit_key=key,
                    limit_value=value,
                )
            )

        # Entitlements: every capability declared by each included module
        for module_name in bundle.get_modules():
            meta = MODULE_REGISTRY.get(module_name)
            if not meta:
                continue
            for capability_key in meta.capabilities:
                db.session.add(
                    PackageVersionEntitlement(
                        package_version_id=version.id,
                        module_name=module_name,
                        capability_key=capability_key,
                    )
                )

        db.session.add(
            PackageVersionAvailability(
                package_version_id=version.id,
                availability_status=PackageVersionAvailabilityStatus.AVAILABLE,
                effective_from=datetime.now(UTC),
            )
        )

        safe_commit(db.session, error_message='database commit failed', reraise=True)
        created_ids.append(package.id)
        if created_package_ids is not None:
            created_package_ids.append(package.id)

    return created_ids


def _sync_package_entitlements_for_bundle(bundle, package) -> None:
    """Bring a package's entitlements into line with its bundle.

    A bundle is the commercial truth: it names the modules a customer buys
    and the price they pay. ``package_version_entitlements`` is the
    activation truth: it is what a tenant actually gets when it buys the
    package. They are supposed to agree, and they did not, because the
    entitlements were written once, when the package was first created, and
    never again.

    So a bundle that was edited - a module added, a module dropped, a name
    corrected - left the package selling the old set. A customer who bought
    the edited bundle got the old set. A customer who bought the bundle
    after a module was dropped from it still got the module. And a bundle
    module whose name was absent from ``MODULE_REGISTRY`` was accepted at
    edit time, produced no entitlement, and was reported as sold at the
    price - a sold module that activated nothing.

    This function makes the entitlements agree with the bundle. It is called
    on every boot (so a bundle edited in the database is reconciled) and
    immediately after a bundle is edited (so the change is live at once).
    Unknown module names are rejected here rather than dropped silently:
    a bundle may not name a module the registry does not know about.
    """
    from app.core.module.registry import MODULE_REGISTRY
    from app.core.tenant.models import ProductBundle

    if not isinstance(bundle, ProductBundle):
        raise SeedError('sync_package_entitlements_for_bundle expects a ProductBundle')

    versions = (
        db.session.execute(select(PackageVersion).filter_by(package_id=package.id)).scalars().all()
    )
    if not versions:
        return

    desired = set(bundle.get_modules())
    unknown = desired - set(MODULE_REGISTRY)
    if unknown:
        raise SeedError(
            f"bundle '{bundle.slug}' names modules that are not in MODULE_REGISTRY: "
            f'{", ".join(sorted(unknown))}'
        )

    for version in versions:
        current = (
            db.session.execute(
                select(PackageVersionEntitlement).filter_by(package_version_id=version.id)
            )
            .scalars()
            .all()
        )
        current_by_module = {}
        for row in current:
            current_by_module.setdefault(row.module_name, []).append(row)

        for module_name in desired:
            meta = MODULE_REGISTRY.get(module_name)
            if meta is None:
                continue
            existing = current_by_module.get(module_name, [])
            if existing:
                # Keep one row; correct the capability keys if the registry
                # changed them. Drop the surplus rows.
                keeper = existing[0]
                keeper.capability_key = meta.capabilities[0] if meta.capabilities else module_name
                for row in existing[1:]:
                    db.session.delete(row)
            else:
                db.session.add(
                    PackageVersionEntitlement(
                        package_version_id=version.id,
                        module_name=module_name,
                        capability_key=meta.capabilities[0] if meta.capabilities else module_name,
                    )
                )

        for module_name in list(current_by_module):
            if module_name not in desired:
                for row in current_by_module[module_name]:
                    db.session.delete(row)

        # A bundle's entitlements are one capability per module today. If a
        # module declares more than one capability, every one of them is a
        # separate entitlement row - otherwise the projection undercounts.
        for module_name in desired:
            meta = MODULE_REGISTRY.get(module_name)
            if meta is None or len(meta.capabilities) <= 1:
                continue
            existing = (
                db.session.execute(
                    select(PackageVersionEntitlement).filter_by(
                        package_version_id=version.id, module_name=module_name
                    )
                )
                .scalars()
                .all()
            )
            have = {r.capability_key for r in existing}
            for capability_key in meta.capabilities[1:]:
                if capability_key not in have:
                    db.session.add(
                        PackageVersionEntitlement(
                            package_version_id=version.id,
                            module_name=module_name,
                            capability_key=capability_key,
                        )
                    )


def sync_package_entitlements_for_bundle(bundle, package) -> None:
    """Reconcile a package's entitlements with its bundle. See the
    definition further down."""
    return _sync_package_entitlements_for_bundle(bundle, package)


def _category_for_bundle(bundle) -> str:
    """Heuristic category for a legacy ProductBundle."""
    modules = bundle.get_modules()
    if len(modules) == 1:
        return 'standalone'
    return 'bundle'
