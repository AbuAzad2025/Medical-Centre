"""
Module subsystem — registry, activation, and decorators
"""

from app.core.module.models import ModuleDefinition, TenantModule
from app.core.module.registry import (
    MODULE_REGISTRY,
    get_all_module_names,
    get_clinical_modules,
    get_feature_flags_for_module,
    get_module_metadata,
    get_modules_by_capability,
    get_standalone_modules,
)
from app.core.module.validators import (
    ModuleValidationError,
    can_activate_module,
    get_active_modules_for_tenant,
    validate_profile_modules,
    validate_reception_required,
)

__all__ = [
    'MODULE_REGISTRY',
    'ModuleDefinition',
    'ModuleValidationError',
    'TenantModule',
    'can_activate_module',
    'get_active_modules_for_tenant',
    'get_all_module_names',
    'get_clinical_modules',
    'get_feature_flags_for_module',
    'get_module_metadata',
    'get_modules_by_capability',
    'get_standalone_modules',
    'validate_profile_modules',
    'validate_reception_required',
]
