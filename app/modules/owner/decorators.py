"""
Owner/SuperAdmin access control decorator.
"""
from functools import wraps
from flask import jsonify, redirect, url_for, flash, current_app
from flask_login import current_user


def owner_required(f):
    """Require super_admin, admin, or owner role. For JSON APIs also checks ENABLE_SAAS_MODE."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            if _is_api():
                return jsonify({"error": "authentication_required"}), 401
            return redirect(url_for('auth.login'))
        if current_user.role not in ('super_admin', 'admin', 'owner'):
            if _is_api():
                return jsonify({"error": "owner_access_required"}), 403
            flash('غير مصرح', 'error')
            return redirect(url_for('main.dashboard'))
        if _is_api() and not current_app.config.get('ENABLE_SAAS_MODE', False):
            return jsonify({"error": "saas_mode_disabled"}), 403
        return f(*args, **kwargs)
    return wrapper


def _is_api():
    """Detect if the request is a JSON API call vs HTML page."""
    from flask import request
    return (request.path.startswith('/owner/api/')
            or request.accept_mimetypes.best == 'application/json'
            or request.path.startswith('/super-admin/api/'))
