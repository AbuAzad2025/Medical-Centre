"""Clinic settings for a solo-doctor clinic that has no manager module."""

from flask import flash, g, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func, select

from app.core.saas.resolver import EntitlementResolver
from app.core.tenant.models import Tenant
from app.extensions import db
from models.user import User
from routes.doctor import doctor_bp
from utils.db_safety import safe_commit
from utils.decorators import role_required

FIELDS = (
    'clinic_name',
    'phone',
    'email',
    'address',
    'working_hours',
    'consultation_fee',
    'follow_up_fee',
)


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
        fee_fields = {'consultation_fee', 'follow_up_fee'}
        for key in FIELDS:
            value = (request.form.get(key) or '').strip()
            if key in fee_fields and value:
                try:
                    amount = float(value)
                except ValueError:
                    flash('رسوم الكشف والمراجعة يجب أن تكون رقماً صحيحاً', 'warning')
                    return redirect(url_for('doctor.clinic_settings'))
                if amount < 0:
                    flash('لا يمكن أن تكون الرسوم سالبة', 'warning')
                    return redirect(url_for('doctor.clinic_settings'))
                value = f'{amount:.2f}'
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

    limits = EntitlementResolver.get_effective_limits(tenant.id)
    seat_limit = limits.get('max_users')
    seat_used = (
        db.session.execute(
            select(func.count()).select_from(User).filter_by(tenant_id=tenant.id)
        ).scalar()
        or 0
    )

    return render_template(
        'doctor/clinic_settings.html',
        tenant=tenant,
        general=general,
        seat_used=seat_used,
        seat_limit=seat_limit,
        can_manage_users=current_user.role in ('super_admin', 'owner'),
    )
