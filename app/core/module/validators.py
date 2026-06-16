"""
Module activation validators — business rules
"""
from app.extensions import db
from app.core.module.models import TenantModule
from app.core.module.registry import get_clinical_modules, MODULE_REGISTRY

class ModuleValidationError(Exception):
    pass


def get_active_modules_for_tenant(tenant_id: int) -> set:
    """Return set of active module names for a tenant."""
    rows = TenantModule.query.filter_by(tenant_id=tenant_id, is_active=True).all()
    return {r.module_name for r in rows}


def validate_reception_required(tenant_id: int, proposed_modules: list[str]):
    """If a tenant wants >2 clinical modules, reception MUST be active."""
    clinical = set(get_clinical_modules())
    proposed_set = set(proposed_modules)
    active = get_active_modules_for_tenant(tenant_id)
    all_clinical = (proposed_set | active) & clinical

    if len(all_clinical) > 3:
        if "reception" not in all_clinical:
            raise ModuleValidationError(
                "Reception module is mandatory when more than 3 clinical modules are active."
            )


def validate_required_any_of(tenant_id: int, module_name: str, active: set):
    """Check that at least one of required_any_of groups is satisfied."""
    meta = MODULE_REGISTRY.get(module_name)
    if not meta or not meta.required_any_of:
        return True, None

    for group in meta.required_any_of:
        if any(req in active or req == module_name for req in group):
            return True, None

    groups_str = " أو ".join(" + ".join(g) for g in meta.required_any_of)
    return False, f"Module '{module_name}' requires one of: {groups_str}"


def can_activate_module(
    tenant_id: int,
    module_name: str,
    profile_code: str | None = None
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
        return False, f"Unknown module: {module_name}"

    # Check required modules
    for req in meta.required_modules:
        if req not in active:
            return False, f"Module '{module_name}' requires '{req}' to be active first."

    # Check required_any_of
    ok, err = validate_required_any_of(tenant_id, module_name, active)
    if not ok:
        return False, err

    # For standalone profiles, check if module is standalone_allowed
    if profile_code and profile_code.startswith("standalone_"):
        if not meta.standalone_allowed and profile_code != "multi_department_center":
            return False, f"Module '{module_name}' is not available as standalone."

    # Check reception rule
    try:
        validate_reception_required(tenant_id, list(active | {module_name}))
    except ModuleValidationError as e:
        return False, str(e)

    return True, None


def validate_profile_modules(profile_code: str, modules: list[str]) -> list[str]:
    """Validate that the module combination makes sense for a profile."""
    errors = []
    from app.core.tenant.models import PRODUCT_PROFILE_DEFAULTS
    profile = PRODUCT_PROFILE_DEFAULTS.get(profile_code)
    if not profile:
        return ["Invalid profile code"]

    if profile_code.startswith("standalone_"):
        for m in modules:
            meta = MODULE_REGISTRY.get(m)
            if meta and not meta.standalone_allowed:
                errors.append(f"Module '{m}' cannot be activated in standalone mode.")
    return errors
