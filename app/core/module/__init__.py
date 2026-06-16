"""
Module subsystem — registry, activation, and decorators
"""
from app.core.module.registry import (
    MODULE_REGISTRY,
    get_module_metadata,
    get_all_module_names,
    get_clinical_modules,
    get_modules_by_capability,
    get_standalone_modules,
    get_feature_flags_for_module,
)
from app.core.module.models import ModuleDefinition, TenantModule
from app.core.module.decorators import module_required
from app.core.module.validators import (
    validate_reception_required,
    get_active_modules_for_tenant,
    can_activate_module,
    validate_profile_modules,
    ModuleValidationError,
)

__all__ = [
    "MODULE_REGISTRY",
    "get_module_metadata",
    "get_all_module_names",
    "get_clinical_modules",
    "get_modules_by_capability",
    "get_standalone_modules",
    "get_feature_flags_for_module",
    "ModuleDefinition",
    "TenantModule",
    "module_required",
    "validate_reception_required",
    "get_active_modules_for_tenant",
    "can_activate_module",
    "validate_profile_modules",
    "ModuleValidationError",
]
