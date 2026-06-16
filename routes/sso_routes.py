"""
SSO / LDAP Configuration Routes
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required
from app_factory import db
from models import SSOConfiguration

sso_bp = Blueprint('sso', __name__)


@sso_bp.route('/config', methods=['GET', 'POST'])
@login_required
def config():
    configs = SSOConfiguration.query.all()
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
        db.session.commit()
        flash('تم إضافة إعدادات SSO', 'success')
        return redirect(url_for('sso.config'))
    return render_template('sso/config.html', configs=configs)


@sso_bp.route('/toggle/<int:config_id>', methods=['POST'])
@login_required
def toggle(config_id):
    cfg = SSOConfiguration.query.get_or_404(config_id)
    cfg.is_active = not cfg.is_active
    db.session.commit()
    flash(f"SSO {'مفعّل' if cfg.is_active else 'معطّل'}", 'success')
    return redirect(url_for('sso.config'))
