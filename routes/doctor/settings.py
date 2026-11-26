"""Clinic settings for a solo-doctor clinic that has no manager module."""

from flask import flash, g, redirect, render_template, request, url_for
from flask_login import login_required

from app.core.tenant.models import Tenant
from app.extensions import db
from routes.doctor import doctor_bp
from utils.db_safety import safe_commit
from utils.decorators import role_required

FIELDS = ('clinic_name', 'phone', 'email', 'address', 'working_hours', 'consultation_fee')


@doctor_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@role_required('doctor', 'admin', 'manager')
def clinic_settings():
    tenant = db.session.get(Tenant, g.tenant_id) if g.tenant_id else None
    if not tenant:
        flash('العيادة غير موجودة', 'error')
        return redirect(url_for('doctor.dashboard'))

    settings = dict(tenant.settings or {})
    general = dict(settings.get('general') or {})
    if request.method == 'POST':
        for key in FIELDS:
            value = (request.form.get(key) or '').strip()
            if value:
                general[key] = value
            else:
                general.pop(key, None)
        settings['general'] = general
        tenant.settings = settings
        if not safe_commit(db.session, error_message='Failed to save clinic settings'):
            flash('تعذر حفظ إعدادات العيادة', 'error')
            return redirect(url_for('doctor.clinic_settings'))
        flash('تم حفظ إعدادات العيادة', 'success')

    return render_template(
        'doctor/clinic_settings.html',
        tenant=tenant,
        general=general,
    )
