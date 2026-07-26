"""
SSO / LDAP Configuration Routes
"""
from sqlalchemy import select
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required
from app.extensions import db
from utils.db_safety import safe_commit, safe_rollback
from models import SSOConfiguration
from services.sso_service import sso_service
from utils.decorators import handle_route_errors

sso_bp = Blueprint('sso', __name__)


@sso_bp.route('/config', methods=['GET', 'POST'])
@login_required
@handle_route_errors
def config():
    configs = db.session.execute(select(SSOConfiguration)).scalars().all()
    if request.method == 'POST':
        cfg = SSOConfiguration(
            name=request.form.get('name', '').strip(),
            provider_type=request.form.get('provider_type', 'ldap'),
            server_url=request.form.get('server_url', '').strip(),
            base_dn=request.form.get('base_dn', '').strip(),
            bind_dn=request.form.get('bind_dn', '').strip(),
            bind_password=request.form.get('bind_password', '').strip(),
            auto_create_user=request.form.get('auto_create_user') == 'on',
            default_role=request.form.get('default_role', 'user')
        )
        db.session.add(cfg)
        safe_commit(db.session, error_message="database commit failed", reraise=True)
        flash('تم إضافة إعدادات SSO', 'success')
        return redirect(url_for('sso.config'))
    return render_template('sso/config.html', configs=configs)


@sso_bp.route('/toggle/<int:config_id>', methods=['POST'])
@login_required
@handle_route_errors
def toggle(config_id):
    cfg = db.get_or_404(SSOConfiguration, config_id)
    cfg.is_active = not cfg.is_active
    safe_commit(db.session, error_message="database commit failed", reraise=True)
    flash(f"SSO {'مفعّل' if cfg.is_active else 'معطّل'}", 'success')
    return redirect(url_for('sso.config'))
