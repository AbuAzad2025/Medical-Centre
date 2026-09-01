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


def _get_bundle_for_tenant(tenant_id: int) -> list[str] | None:
    """Return allowed module names from the tenant's ProductBundle, or None if unrestricted."""
    from app.core.tenant.models import Tenant, get_bundle_for_profile

    tenant = db.session.get(Tenant, tenant_id)
    if not tenant or not tenant.product_profile_code:
        return None  # No bundle restriction
    bundle = get_bundle_for_profile(tenant.product_profile_code)
    if bundle:
        return bundle.get_modules()
    return None


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

    # Dynamic bundle boundary enforcement
    allowed = _get_bundle_for_tenant(tenant_id)
    if allowed is not None and module_name not in allowed:
        return (
            False,
            f"Module '{module_name}' is not included in the tenant's bundle. "
            f"Allowed modules: {', '.join(allowed)}.",
        )

    return True, None


def validate_profile_modules(profile_code: str, modules: list[str]) -> list[str]:
    """Validate that the module combination makes sense for a profile.
    Non-blocking: returns empty list (no restrictions)."""
    return []
