from app.shared.http_errors import SubscriptionRequired  # noqa: E402

"""
FeatureGateService — Unified feature/module/action gating
"""

from functools import wraps

from flask import abort, current_app, g
from flask_login import current_user
from sqlalchemy import select

from app.core.module.validators import get_active_modules_for_tenant
from app.extensions import db
from app.shared.enums import TenantStatus
from app.shared.user_role_policy import normalize_role


class ModuleNotEnabledError(Exception):
    """Raised when a service method requires a module that is not enabled for the tenant."""

    def __init__(self, module_name: str, message: str | None = None):
        self.module_name = module_name
        self.message = message or f"Module '{module_name}' is not enabled for this tenant"
        super().__init__(self.message)


class FeatureNotEnabledError(Exception):
    """Raised when a service method requires a feature that is not enabled."""

    def __init__(self, feature_name: str, message: str | None = None):
        self.feature_name = feature_name
        self.message = message or f"Feature '{feature_name}' is not enabled"
        super().__init__(self.message)


def _is_admin_user() -> bool:
    try:
        return current_user.is_authenticated and normalize_role(current_user.role) in (
            'super_admin',
            'owner',
            'admin',
            'platform_owner',
        )
    except Exception:
        return False


def _check_tenant_payment_status(tenant) -> bool:
    """Check if tenant has valid payment status for module access.
    Returns True if tenant is ACTIVE or TRIAL, False if PENDING/PAST_DUE/CANCELLED.
    If tenant doesn't have status attribute, assume valid (backward compatibility).
    """
    status = getattr(tenant, 'status', None)
    if status is None:
        return True  # Backward compatibility for tests/mock tenants
    return status in (TenantStatus.ACTIVE, TenantStatus.TRIAL)


class FeatureGateService:
    @staticmethod
    def module_enabled(tenant_id: int, module: str) -> bool:
        return module in get_active_modules_for_tenant(tenant_id)

    @staticmethod
    def feature_enabled(tenant_id: int, feature: str) -> bool:
        from app.core.tenant.models import TenantFeatureFlag

        flag = (
            db.session.execute(
                select(TenantFeatureFlag).filter_by(
                    tenant_id=tenant_id, feature_key=feature, is_enabled=True
                )
            )
            .scalars()
            .first()
        )
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

        tenant = db.session.get(Tenant, tenant_id)  # global reference table - no tenant scope
        return tenant.product_profile_code if tenant else None

    @staticmethod
    def tenant_has_valid_payment(tenant) -> bool:
        """Check if tenant has valid payment status for module access."""
        return _check_tenant_payment_status(tenant)


def require_module(module: str):
    """
    Decorator for service methods that require a module to be enabled.
    Raises ModuleNotEnabledError if the module is not enabled for the current tenant.
    Skips check when ENABLE_SAAS_MODE is False (standalone mode).
    Admin and super_admin users bypass only non-clinical module checks (reporting/billing).
    """

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_app.config.get('ENABLE_SAAS_MODE', False):
                return f(*args, **kwargs)
            if _is_admin_user() and module in ('reporting', 'billing', 'appointments', 'inventory'):
                return f(*args, **kwargs)
            tenant = getattr(g, 'current_tenant', None)
            if not tenant:
                raise ModuleNotEnabledError(module, 'Tenant context required')
            if not FeatureGateService.tenant_has_valid_payment(tenant):
                raise ModuleNotEnabledError(module, 'Subscription payment required')
            if not FeatureGateService.module_enabled(tenant.id, module):
                raise ModuleNotEnabledError(module)
            return f(*args, **kwargs)

        return wrapper

    return decorator


def require_module_route(module: str):
    """
    Decorator for route handlers that require a module to be enabled.
    Aborts with 403 if the module is not enabled (HTTP response).
    Use this for route handlers; use require_module for service methods.
    """

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_app.config.get('ENABLE_SAAS_MODE', False):
                return f(*args, **kwargs)
            if _is_admin_user() and module in ('reporting', 'billing', 'appointments', 'inventory'):
                return f(*args, **kwargs)
            tenant = getattr(g, 'current_tenant', None)
            if not tenant:
                abort(403, description='Tenant context required')
            if not FeatureGateService.tenant_has_valid_payment(tenant):
                raise SubscriptionRequired('هذه الميزة تتطلب ترقية الباقة')
            if not FeatureGateService.module_enabled(tenant.id, module):
                abort(403, description=f"Module '{module}' is not enabled")
            return f(*args, **kwargs)

        return wrapper

    return decorator


def guard_module(module_name: str):
    """Blueprint before_request guard: 403 if module not enabled for tenant.
    Skips check when ENABLE_SAAS_MODE is False (standalone mode).
    Admin and super_admin bypass only non-clinical guards.
    """
    if not current_app.config.get('ENABLE_SAAS_MODE', False):
        return
    if _is_admin_user() and module_name in ('reporting', 'billing', 'appointments', 'inventory'):
        return
    tenant = getattr(g, 'current_tenant', None)
    if not tenant:
        abort(403, description='Tenant context required for module access')
    if not FeatureGateService.tenant_has_valid_payment(tenant):
        raise SubscriptionRequired('هذه الميزة تتطلب ترقية الباقة')
    if not FeatureGateService.module_enabled(tenant.id, module_name):
        abort(403, description=f"Module '{module_name}' is not enabled")


def require_feature(feature: str):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_app.config.get('ENABLE_SAAS_MODE', False):
                return f(*args, **kwargs)
            if _is_admin_user() and feature in ('reporting', 'billing'):
                return f(*args, **kwargs)
            tenant = getattr(g, 'current_tenant', None)
            if not tenant:
                abort(403, description='Tenant context required')
            if not FeatureGateService.feature_enabled(tenant.id, feature):
                abort(403, description=f"Feature '{feature}' is not enabled")
            return f(*args, **kwargs)

        return wrapper

    return decorator


def require_feature_service(feature: str):
    """
    Decorator for service methods that require a feature flag to be enabled.
    Raises FeatureNotEnabledError if the feature is not enabled.
    """

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_app.config.get('ENABLE_SAAS_MODE', False):
                return f(*args, **kwargs)
            if _is_admin_user():
                return f(*args, **kwargs)
            tenant = getattr(g, 'current_tenant', None)
            if not tenant:
                raise FeatureNotEnabledError(feature, 'Tenant context required')
            if not FeatureGateService.feature_enabled(tenant.id, feature):
                raise FeatureNotEnabledError(feature)
            return f(*args, **kwargs)

        return wrapper

    return decorator
