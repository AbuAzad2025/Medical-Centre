"""
PermissionService — unified DB-driven + fallback role-based permission checking
"""
import logging
from flask_login import current_user
from app.extensions import db

logger = logging.getLogger(__name__)

# Fallback role-permission map (hardcoded only as graceful degradation)
ROLE_PERMISSIONS = {
    "super_admin": {"*"},  # wildcard
    "admin": {
        "user.*", "patient.*", "visit.*", "appointment.*",
        "department.*", "report.*", "setting.*", "audit.*",
    },
    "manager": {
        "patient.read", "patient.update", "visit.read", "visit.update",
        "report.read", "report.create", "financial.*",
    },
    "doctor": {
        "patient.read", "visit.read", "visit.update", "prescription.*",
        "lab_order.*", "radiology_order.*", "medical_record.*",
    },
    "reception": {
        "patient.*", "visit.*", "appointment.*", "payment.*",
        "queue.*", "receipt.*",
    },
    "lab": {
        "lab_request.read", "lab_request.update", "lab_result.*",
        "patient.read",
    },
    "radiology": {
        "radiology_request.read", "radiology_request.update", "radiology_result.*",
        "patient.read",
    },
    "pharmacist": {
        "pharmacy.*", "prescription.read", "patient.read",
    },
    "emergency": {
        "emergency.*", "patient.read", "patient.update", "visit.*",
    },
    "nurse": {
        "patient.read", "patient.update", "nurse.*", "visit.read",
    },
    "accountant": {
        "financial.*", "invoice.*", "payment.*", "report.read",
    },
}


class PermissionService:
    """Centralized permission resolver.

    Priority:
      1. DB RolePermission table (if initialized)
      2. Fallback ROLE_PERMISSIONS dict
    """

    @staticmethod
    def has_permission(user, permission: str) -> bool:
        if not user or not getattr(user, "is_authenticated", False):
            return False

        # Wildcard super-admin
        if getattr(user, "role", None) == "super_admin":
            return True

        # 1. Try DB-driven permissions
        try:
            from sqlalchemy import inspect
            from models.permissions import Role, Permission as Perm, RolePermission

            insp = inspect(db.engine)
            if insp.has_table("roles") and insp.has_table("permissions"):
                role = Role.query.filter_by(name=user.role, is_active=True).first()
                if role:
                    perm = Perm.query.filter_by(name=permission, is_active=True).first()
                    if perm:
                        ok = RolePermission.query.filter_by(role_id=role.id, permission_id=perm.id).first()
                        if ok:
                            return True
        except Exception:
            pass

        # 2. Fallback role map
        role_perms = ROLE_PERMISSIONS.get(user.role, set())
        if "*" in role_perms:
            return True
        # Support wildcard segments: user.* matches user.read
        for rp in role_perms:
            if rp == permission:
                return True
            if rp.endswith(".*") and permission.startswith(rp[:-1]):
                return True
        return False

    @staticmethod
    def require(permission: str):
        """Decorator factory — use @PermissionService.require('action.resource')"""
        from functools import wraps
        from flask import abort

        def decorator(f):
            @wraps(f)
            def wrapper(*args, **kwargs):
                if not PermissionService.has_permission(current_user, permission):
                    abort(403)
                return f(*args, **kwargs)
            return wrapper
        return decorator
