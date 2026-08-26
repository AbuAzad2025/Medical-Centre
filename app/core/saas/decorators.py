"""
SaaS entitlement route decorators — S0-004

Composes with existing role/permission decorators:
    @require_entitlement("lab.order")
    @PermissionService.require("lab_order.create")
    def create_lab_order(...):
        ...
"""

from functools import wraps

from flask import abort, current_app, g
from flask_login import current_user

from app.core.saas.resolver import EntitlementResolver
from app.extensions import db

_BYPASS_ROLES = frozenset({'super_admin', 'owner', 'platform_owner'})


def _is_admin_user() -> bool:
    try:
        return current_user.is_authenticated and current_user.role in _BYPASS_ROLES
    except Exception:
        return False


def _is_json_request() -> bool:
    try:
        from flask import request

        return request.accept_mimetypes.best == 'application/json' or request.is_json
    except Exception:
        return False


def require_entitlement(capability_key: str):
    """Route decorator: abort 403 if current tenant lacks the capability.
    Admin and super_admin bypass all entitlement checks.
    """

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_app.config.get('ENABLE_SAAS_MODE', False):
                return f(*args, **kwargs)

            if _is_admin_user():
                return f(*args, **kwargs)

            from app.core.tenant.models import Tenant
            from app.core.tenant.service import TenantContextService

            tenant = getattr(g, 'current_tenant', None) or TenantContextService.get_current_tenant()
            if tenant is None and getattr(g, 'tenant_id', None):
                tenant = db.session.get(Tenant, g.tenant_id)
            if tenant is None:
                abort(403, description='Tenant context required.')

            if not EntitlementResolver.is_entitled(tenant.id, capability_key):
                if _is_json_request():
                    from flask import jsonify

                    return jsonify(
                        {'error': 'entitlement_required', 'capability': capability_key}
                    ), 403
                abort(403, description=f"Tenant not entitled to '{capability_key}'.")

            return f(*args, **kwargs)

        return wrapper

    return decorator
