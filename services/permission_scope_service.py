"""
Permission Scope Service - resolves what data a user can access based on module roles
"""
from typing import List, Optional
from flask import g


class PermissionScopeService:
    """Determines data access scope based on user's active modules and role."""

    @staticmethod
    def get_accessible_tenant_ids(user_id: int) -> List[int]:
        """Return tenant IDs the user can access (all if super admin, else assigned)."""
        from models.user import User
        from models.tenant import Tenant

        user = User.query.get(user_id)
        if not user:
            return []
        if hasattr(user, 'is_super_admin') and user.is_super_admin:
            return [t.id for t in Tenant.query.all()]
        if hasattr(user, 'tenant_id') and user.tenant_id:
            return [user.tenant_id]
        return []

    @staticmethod
    def get_accessible_module_names(user_id: int, tenant_id: Optional[int] = None) -> List[str]:
        """Return module names the user can access within a tenant."""
        from models.tenant import TenantFeatureFlag
        from models.user import User
        from models.advanced_permissions import ModulePermission

        user = User.query.get(user_id)
        if not user:
            return []
        if user.is_super_admin:
            return ['reception', 'doctor', 'lab', 'radiology', 'emergency', 'accounting',
                    'pharmacy', 'billing', 'nursing', 'appointments', 'inventory',
                    'portal', 'dicom', 'ai_imaging', 'admin', 'manager']

        tid = tenant_id or (user.tenant_id if hasattr(user, 'tenant_id') else None)
        if not tid:
            return []

        features = TenantFeatureFlag.query.filter_by(tenant_id=tid, is_active=True).all()
        enabled_modules = [f.module for f in features if f.module]

        role_id = user.role_id if hasattr(user, 'role_id') else None
        if not role_id:
            return enabled_modules

        perms = ModulePermission.query.filter_by(role_id=role_id).all()
        permitted_modules = [p.module_name for p in perms if p.can_view]

        return [m for m in enabled_modules if m in permitted_modules]
