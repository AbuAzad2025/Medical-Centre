"""
SaaS entitlement route decorators — S0-004

Composes with existing role/permission decorators:
    @require_entitlement("lab.order")
    @PermissionService.require("lab_order.create")
    def create_lab_order(...):
        ...
"""

from functools import wraps

from flask import abort, g, current_app
from flask_login import current_user

from app.core.saas.resolver import EntitlementResolver


def _is_admin_user() -> bool:
    """True if the current user is a global super_admin bypassing tenant restrictions."""
    try:
        return current_user.is_authenticated and current_user.role == "super_admin"
    except Exception:
        return False


def require_entitlement(capability_key: str):
    """Route decorator: abort 403 if current tenant lacks the capability.
    Admin and super_admin bypass all entitlement checks.
    """

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_app.config.get("ENABLE_SAAS_MODE", False):
                return f(*args, **kwargs)

            if _is_admin_user():
                return f(*args, **kwargs)

            from app.core.tenant.service import TenantContextService
            from app.core.tenant.models import Tenant

            tenant = getattr(g, "current_tenant", None) or TenantContextService.get_current_tenant()
            if tenant is None and getattr(g, "tenant_id", None):
                tenant = Tenant.query.get(g.tenant_id)
            if tenant is None:
                abort(403, description="Tenant context required.")

            if not EntitlementResolver.is_entitled(tenant.id, capability_key):
                abort(403, description=f"Tenant not entitled to '{capability_key}'.")

            return f(*args, **kwargs)

        return wrapper

    return decorator
