"""
SaaS entitlement route decorators — S0-004

Composes with existing role/permission decorators:
    @require_entitlement("lab.order")
    @PermissionService.require("lab_order.create")
    def create_lab_order(...):
        ...
"""

from functools import wraps

from flask import abort, g

from app.core.saas.resolver import EntitlementResolver


def require_entitlement(capability_key: str):
    """Route decorator: abort 403 if current tenant lacks the capability."""

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            tenant = getattr(g, "current_tenant", None)
            if tenant is None:
                abort(403, description="Tenant context required.")

            if not EntitlementResolver.is_entitled(tenant.id, capability_key):
                abort(403, description=f"Tenant not entitled to '{capability_key}'.")

            return f(*args, **kwargs)

        return wrapper

    return decorator
