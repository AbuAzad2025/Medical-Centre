"""
Permission decorators — thin wrappers around PermissionService
"""
from functools import wraps
from flask import abort
from flask_login import current_user
from app.core.permission.service import PermissionService


def permission_required(permission: str):
    """Route decorator: abort 403 if current_user lacks permission."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not PermissionService.has_permission(current_user, permission):
                abort(403, description=f"Permission '{permission}' required.")
            return f(*args, **kwargs)
        return wrapper
    return decorator
