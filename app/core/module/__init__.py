"""
Module subsystem — registry, activation, and decorators
"""
from app.core.module.registry import MODULE_REGISTRY, get_module_metadata
from app.core.module.models import ModuleDefinition, TenantModule
from app.core.module.decorators import module_required
from app.core.module.validators import validate_reception_required, get_active_modules_for_tenant

__all__ = [
    "MODULE_REGISTRY",
    "get_module_metadata",
    "ModuleDefinition",
    "TenantModule",
    "module_required",
    "validate_reception_required",
    "get_active_modules_for_tenant",
]
