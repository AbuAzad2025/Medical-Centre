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


def _category_for_bundle(bundle) -> str:
    """Heuristic category for a legacy ProductBundle."""
    modules = bundle.get_modules()
    if len(modules) == 1:
        return 'standalone'
    return 'bundle'
