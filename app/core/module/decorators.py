"""
Module-required decorator
"""
from functools import wraps
from flask import abort, g
from app.core.module.validators import get_active_modules_for_tenant


def module_required(module_name: str):
    """Decorator: abort 403 if the current tenant does not have this module active."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            tenant = getattr(g, 'current_tenant', None)
            if not tenant:
                # Single-tenant legacy mode: allow
                return f(*args, **kwargs)
            active = get_active_modules_for_tenant(tenant.id)
            if module_name not in active:
                abort(403, description=f"Module '{module_name}' is not activated for this tenant.")
            return f(*args, **kwargs)
        return decorated_function
    return decorator
