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


def can_activate_module(
    tenant_id: int, module_name: str, profile_code: str | None = None
) -> tuple[bool, str | None]:
    """
    Check whether a module can be activated for a tenant.
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

    # No required_any_of, no standalone_allowed check, no reception rule
    # Any module can be activated freely as long as hard deps are met

    return True, None


def validate_profile_modules(profile_code: str, modules: list[str]) -> list[str]:
    """Validate that the module combination makes sense for a profile.
    Non-blocking: returns empty list (no restrictions)."""
    return []
