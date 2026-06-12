"""
Module activation validators — business rules
"""
from app.extensions import db
from app.core.module.models import TenantModule
from app.core.module.registry import get_clinical_modules

class ModuleValidationError(Exception):
    pass


def get_active_modules_for_tenant(tenant_id: int) -> set:
    """Return set of active module names for a tenant."""
    rows = TenantModule.query.filter_by(tenant_id=tenant_id, is_active=True).all()
    return {r.module_name for r in rows}


def validate_reception_required(tenant_id: int, proposed_modules: list[str]):
    """
    Business rule: If a tenant wants >2 clinical modules,
    reception MUST be active.
    """
    clinical = set(get_clinical_modules())
    proposed_set = set(proposed_modules)
    active = get_active_modules_for_tenant(tenant_id)

    # Include already-active modules in the count
    all_clinical = (proposed_set | active) & clinical

    if len(all_clinical) > 2:
        if "reception" not in all_clinical:
            raise ModuleValidationError(
                "Reception module is mandatory when more than 2 clinical modules are active."
            )


def can_activate_module(tenant_id: int, module_name: str) -> tuple[bool, str | None]:
    """
    Check whether a module can be activated for a tenant.
    Returns (ok, error_message).
    """
    active = get_active_modules_for_tenant(tenant_id)
    if module_name in active:
        return True, None  # Already active

    from app.core.module.registry import MODULE_REGISTRY
    meta = MODULE_REGISTRY.get(module_name)
    if not meta:
        return False, f"Unknown module: {module_name}"

    # Check required modules
    for req in meta.required_modules:
        if req not in active:
            return False, f"Module '{module_name}' requires '{req}' to be active first."

    # Check reception rule
    try:
        validate_reception_required(tenant_id, list(active | {module_name}))
    except ModuleValidationError as e:
        return False, str(e)

    return True, None
