"""
FeatureGateService — Unified feature/module/action gating
"""
from functools import wraps
from flask import g, abort, current_app
from app.core.module.validators import get_active_modules_for_tenant

class FeatureGateService:
    @staticmethod
    def module_enabled(tenant_id: int, module: str) -> bool:
        return module in get_active_modules_for_tenant(tenant_id)

    @staticmethod
    def feature_enabled(tenant_id: int, feature: str) -> bool:
        from app.core.tenant.models import TenantFeatureFlag
        flag = TenantFeatureFlag.query.filter_by(tenant_id=tenant_id, feature_key=feature, is_enabled=True).first()
        return flag is not None

    @staticmethod
    def can_use(user, action: str) -> bool:
        try:
            from services.access_control_service import AccessControlService
            return AccessControlService.user_has_permission(user, action)
        except Exception:
            return True

    @staticmethod
    def product_profile(tenant_id: int) -> str | None:
        from app.core.tenant.models import Tenant
        tenant = Tenant.query.get(tenant_id)
        return tenant.product_profile_code if tenant else None

def require_module(module: str):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_app.config.get('ENABLE_SAAS_MODE', False):
                return f(*args, **kwargs)
            tenant = getattr(g, 'current_tenant', None)
            if not tenant:
                abort(403, description="Tenant context required")
            if not FeatureGateService.module_enabled(tenant.id, module):
                abort(403, description=f"Module '{module}' is not enabled")
            return f(*args, **kwargs)
        return wrapper
    return decorator

def guard_module(module_name: str):
    """Blueprint before_request guard: 403 if module not enabled for tenant.
    Skips check when ENABLE_SAAS_MODE is False (standalone mode).
    """
    if not current_app.config.get('ENABLE_SAAS_MODE', False):
        return
    tenant = getattr(g, 'current_tenant', None)
    if not tenant:
        return
    if not FeatureGateService.module_enabled(tenant.id, module_name):
        abort(403, description=f"Module '{module_name}' is not enabled")

def require_feature(feature: str):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_app.config.get('ENABLE_SAAS_MODE', False):
                return f(*args, **kwargs)
            tenant = getattr(g, 'current_tenant', None)
            if not tenant:
                abort(403, description="Tenant context required")
            if not FeatureGateService.feature_enabled(tenant.id, feature):
                abort(403, description=f"Feature '{feature}' is not enabled")
            return f(*args, **kwargs)
        return wrapper
    return decorator