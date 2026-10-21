"""
SSO / LDAP Configuration Routes
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy import select

from app.extensions import db
from models import SSOConfiguration
from utils.db_safety import safe_commit
from utils.decorators import handle_route_errors, role_required

sso_bp = Blueprint('sso', __name__)

# The roles an SSO provider may hand to an account it creates. A provider
# that creates users must not create privileged ones: the role is what a
# successful SSO login is granted, so a configurable privileged role is a
# standing escalation for whoever can write the configuration.
_SSO_ASSIGNABLE_ROLES = frozenset({'user', 'patient', 'nurse', 'doctor', 'pharmacist', 'reception'})


@sso_bp.route('/config', methods=['GET', 'POST'])
@login_required
@role_required('super_admin', 'owner')
@handle_route_errors
def config():
    """Identity-provider configuration.

    Writing this registers an identity provider, stores a bind credential and
    can set ``default_role`` to ``super_admin`` with ``auto_create_user`` on.
    That is a standing privilege-escalation primitive once the SSO login flow
    is enabled, so it is restricted to the platform owners rather than to
    anybody who is signed in.
    """
    configs = db.session.execute(select(SSOConfiguration)).scalars().all()
    if request.method == 'POST':
        # A provider that creates users must not create privileged ones. The
        # role is what a successful SSO login is granted, so an account that
        # can set it to super_admin can hand that role to anyone it names.
        default_role = (request.form.get('default_role') or 'user').strip().lower()
        if default_role not in _SSO_ASSIGNABLE_ROLES:
            default_role = 'user'
        cfg = SSOConfiguration(
            name=request.form.get('name', '').strip(),
            provider_type=request.form.get('provider_type', 'ldap'),
            server_url=request.form.get('server_url', '').strip(),
            base_dn=request.form.get('base_dn', '').strip(),
            bind_dn=request.form.get('bind_dn', '').strip(),
            bind_password=request.form.get('bind_password', '').strip(),
            auto_create_user=request.form.get('auto_create_user') == 'on',
            default_role=default_role,
        )
        db.session.add(cfg)
        safe_commit(db.session, error_message='database commit failed', reraise=True)
        flash('تم إضافة إعدادات SSO', 'success')
        return redirect(url_for('sso.config'))
    return render_template('sso/config.html', configs=configs)


@sso_bp.route('/toggle/<int:config_id>', methods=['POST'])
@login_required
@role_required('super_admin', 'owner')
@handle_route_errors
def toggle(config_id):
    cfg = db.get_or_404(SSOConfiguration, config_id)
    cfg.is_active = not cfg.is_active
    safe_commit(db.session, error_message='database commit failed', reraise=True)
    flash(f'SSO {"مفعّل" if cfg.is_active else "معطّل"}', 'success')
    return redirect(url_for('sso.config'))
