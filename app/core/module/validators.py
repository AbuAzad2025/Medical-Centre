"""
Module activation validators — business rules (minimal, non-blocking)
"""

from sqlalchemy import select

from app.core.module.models import TenantModule
from app.core.module.registry import MODULE_REGISTRY
from app.extensions import db


class ModuleValidationError(Exception):
    pass


def get_active_modules_for_tenant(tenant_id: int) -> set:
    """Return set of active module names for a tenant."""
    rows = (
        db.session.execute(select(TenantModule).filter_by(tenant_id=tenant_id, is_active=True))
        .scalars()
        .all()
    )
    return {r.module_name for r in rows}


def get_module_scope_for_tenant(tenant_id: int) -> tuple[bool, frozenset[str]]:
    """The tenant's module boundary: is it inside one, and what is switched on.

    The first value is True when the tenant has rows in ``tenant_modules`` at
    all. That is the same rule the route guard uses (``module_gate_active``):
    a tenant that never opted into the module system has no boundary to
    enforce, and every module stays available to it. That is the single-install
    clinic, and a boundary that failed closed there would lock it out of the
    features it has always had.

    The second value is what is switched on, not what was bought. A module the
    tenant bought and then switched off is off, and the rows it touches are
    not the tenant's to reach through another module's route.

    One query answers both. The two facts were read separately elsewhere, and
    the second one alone cannot tell "no module set" from "every module
    switched off" - the difference between an unrestricted clinic and a
    restricted one.
    """
    rows = db.session.execute(
        select(TenantModule.module_name, TenantModule.is_active).filter_by(tenant_id=tenant_id)
    ).all()
    if not rows:
        return False, frozenset()
    return True, frozenset(name for name, is_active in rows if is_active)


def get_purchased_modules_for_tenant(tenant_id: int) -> set[str] | None:
    """The modules this tenant has bought, or None when it is unrestricted.

    This is the commercial boundary, and it is the question "what is this
    tenant paying for?". It is answered from what the tenant actually
    bought, in the order of authority:

      1. the entitlements of the package on its active subscription - this
         is the purchase, and it is what the customer paid for;
      2. the modules on the tenant's plan, for the older plans that carry
         their module list themselves;
      3. the modules of the tenant's product bundle, for a tenant that was
         provisioned from a bundle.

    None means "no boundary": the tenant has no subscription and no bundle
    and no plan, so there is nothing to be inside of. That is the state of a
    single-install clinic that never opted into the module system, and it
    must not be confused with a tenant that bought a small bundle.

    The previous answer to this question read only
    ``tenant.product_profile_code``, which is NULL for every tenant that
    signed itself up - the signup form posts a package version and no
    profile. So the boundary did not exist for exactly the tenants that
    chose their own package, and the self-service module switch could turn
    on anything in the registry.
    """
    from app.core.saas.models import PackageVersionEntitlement, SubscriptionLine
    from app.core.tenant.models import Tenant

    tenant = db.session.get(Tenant, tenant_id)
    if not tenant:
        return None

    # 1. The package on the active subscription.
    try:
        line = (
            db.session.execute(
                select(SubscriptionLine)
                .filter_by(tenant_id=tenant_id)
                .order_by(SubscriptionLine.id.desc())
            )
            .scalars()
            .first()
        )
        if line is not None and line.package_version_id:
            rows = (
                db.session.execute(
                    select(PackageVersionEntitlement).filter_by(
                        package_version_id=line.package_version_id
                    )
                )
                .scalars()
                .all()
            )
            if rows:
                return {r.module_name for r in rows if r.module_name}
    except Exception as exc:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).warning('purchase boundary: %s', exc)

    # 2. The tenant's own plan.
    try:
        import json

        from app.core.tenant.models import SubscriptionPlan

        plan_id = getattr(tenant, 'plan_id', None)
        if plan_id:
            plan = db.session.get(SubscriptionPlan, plan_id)
            raw = getattr(plan, 'modules_included', None) if plan else None
            if raw:
                mods = json.loads(raw) if isinstance(raw, str) else raw
                if isinstance(mods, list) and mods:
                    return {m for m in mods if m}
    except Exception as exc:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).warning('purchase boundary: %s', exc)

    # 3. The product bundle the tenant was provisioned from.
    from app.core.tenant.models import get_bundle_for_profile

    profile = getattr(tenant, 'product_profile_code', None)
    if profile:
        bundle = get_bundle_for_profile(profile)
        if bundle:
            return set(bundle.get_modules())

    return None


def _get_bundle_for_tenant(tenant_id: int) -> list[str] | None:
    """The modules the tenant has bought, as a list, or None if unrestricted.

    The seam the module validators go through. It is answered from what the
    tenant paid for, not only from its product profile: the profile code is
    NULL for every tenant that signed itself up, so reading only that left
    the boundary open for exactly the tenants that chose their own package.
    """
    purchased = get_purchased_modules_for_tenant(tenant_id)
    if purchased is None:
        return None
    return sorted(purchased)


def can_activate_module(
    tenant_id: int, module_name: str, profile_code: str | None = None
) -> tuple[bool, str | None]:
    """
    Check whether a module can be activated for a tenant.
    Enforces bundle boundaries: if the tenant has a product_profile_code,
    only modules listed in that bundle are allowed.
    Returns (ok, error_message).
    """
    active = get_active_modules_for_tenant(tenant_id)
    if module_name in active:
        return True, None

    meta = MODULE_REGISTRY.get(module_name)
    if not meta:
        return False, f'Unknown module: {module_name}'

    # Check required modules (hard dependencies only)
    for req in meta.required_modules:
        if req not in active:
            return False, f"Module '{module_name}' requires '{req}' to be active first."

    # The commercial boundary: the module has to be one the tenant bought.
    # This is read from what the tenant paid for, not only from the profile
    # code - the profile code is NULL for every tenant that signed itself
    # up, so reading only that left the boundary open for exactly the
    # tenants that picked their own package.
    allowed = _get_bundle_for_tenant(tenant_id)
    if allowed is not None and module_name not in allowed:
        return (
            False,
            f"Module '{module_name}' is not included in the tenant's bundle. "
            f'Allowed modules: {", ".join(sorted(allowed))}.',
        )

    return True, None


def validate_profile_modules(profile_code: str, modules: list[str]) -> list[str]:
    """Validate that the module combination makes sense for a profile.
    Non-blocking: returns empty list (no restrictions)."""
    return []
