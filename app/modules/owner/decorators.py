"""
Owner/SuperAdmin access control decorator — S0-007 security contract.

Platform owner area is strictly separated from tenant administrators.
Only cross-tenant platform roles may access /owner/* surfaces.
"""
from functools import wraps

from flask import jsonify, redirect, url_for, flash, current_app, request
from flask_login import current_user

_PLATFORM_ROLES = frozenset({"super_admin", "owner"})
_SENSITIVE_API_PREFIXES = (
    "/owner/api/tenants/provision",
    "/owner/api/tenants/",
    "/owner/api/bundles",
)


def owner_required(f):
    """Require platform owner role. Tenant-scoped admins are rejected."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            if _is_api():
                return jsonify({"error": "authentication_required"}), 401
            return redirect(url_for('auth.login'))

        if current_user.role not in _PLATFORM_ROLES:
            if _is_api():
                return jsonify({"error": "platform_owner_access_required"}), 403
            flash('غير مصرح — منطقة إدارة المنصة فقط', 'error')
            return redirect(url_for('main.dashboard'))

        if _is_api() and not current_app.config.get('ENABLE_SAAS_MODE', False):
            return jsonify({"error": "saas_mode_disabled"}), 403

        if _is_sensitive_owner_api():
            _audit_owner_api_access()

        return f(*args, **kwargs)
    return wrapper


def _is_api():
    return (
        request.path.startswith('/owner/api/')
        or request.accept_mimetypes.best == 'application/json'
        or request.path.startswith('/super-admin/api/')
    )


def _is_sensitive_owner_api() -> bool:
    path = request.path or ""
    return any(path.startswith(prefix) for prefix in _SENSITIVE_API_PREFIXES)


def _audit_owner_api_access() -> None:
    try:
        from app.extensions import db
        from app.core.tenant.models import PlatformAuditLog

        log = PlatformAuditLog(
            user_id=getattr(current_user, "id", None),
            tenant_id=getattr(current_user, "tenant_id", None),
            action="OWNER_API_ACCESS",
            entity_type="owner_route",
            entity_id=None,
            details=f"path={request.path}, method={request.method}",
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        from app.extensions import db
        db.session.rollback()
