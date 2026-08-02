"""
المسارات الرئيسية - Main Routes
Medical System Main Routes
"""

from datetime import UTC

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from services.dashboard_routing import get_package_restricted_context, resolve_dashboard_for_user

main_bp = Blueprint('main', __name__)


@main_bp.get('/')
def index():
    """الصفحة الرئيسية — عرض المنصة والحزم"""
    if current_user.is_authenticated:
        return redirect(url_for(resolve_dashboard_for_user(current_user)))
    from app.core.tenant.models import ProductBundle

    bundles = db.session.execute(select(ProductBundle).order_by(ProductBundle.id)).scalars().all()
    # Group bundles by category for display
    cats = {
        'عيادات': [
            'private_doctor_clinic',
            'doctor_clinic_reception',
            'doctor_clinic_full',
            'small_clinic',
            'clinic_with_lab',
            'clinic_with_radiology',
            'clinic_with_lab_radiology',
            'walkin_clinic',
        ],
        'مختبرات وأشعة': [
            'standalone_lab',
            'lab_with_reception',
            'standalone_radiology',
            'radiology_with_reception',
        ],
        'صيدليات وطوارئ': ['standalone_pharmacy', 'standalone_emergency'],
        'مراكز متخصصة': ['urgent_care', 'diagnostic_center', 'community_clinic', 'nursing_home'],
        'مؤسسات كبرى': ['multi_department_center', 'polyclinic', 'hospital'],
        'حزم أخرى': ['billing_only', 'custom'],
    }
    by_code = {b.profile_code: b for b in bundles}
    grouped = []
    for cat_name, codes in cats.items():
        items = [by_code[c] for c in codes if c in by_code]
        if items:
            grouped.append({'cat': cat_name, 'list': items})
    return render_template('main/landing.html', grouped=grouped)


@main_bp.route('/dashboard')
@login_required
def dashboard():
    """لوحة التحكم الرئيسية - إعادة توجيه صارمة حسب الدور والحزمة النشطة"""
    return redirect(url_for(resolve_dashboard_for_user(current_user)))


@main_bp.route('/package-restricted')
@login_required
def package_restricted():
    """صفحة رفض الوصول - الدور لا يتطابق مع الحزمة النشطة"""
    ctx = get_package_restricted_context(current_user)
    return render_template('main/package_restricted.html', **ctx)


# تم نقل /profile إلى auth_routes.py

# تم نقل /profile إلى auth_routes.py


@main_bp.route('/appointments')
@login_required
def appointments_redirect():
    """إعادة توجيه المواعيد حسب الدور"""
    role = current_user.role
    if role == 'doctor':
        return redirect(url_for('doctor.appointments'))
    if role == 'reception':
        return redirect(url_for('reception.appointments'))
    if role == 'patient':
        return redirect(url_for('portal.appointments'))
    return redirect(url_for('reception.appointments'))


@main_bp.route('/settings')
@login_required
def settings():
    """الإعدادات"""
    return render_template('main/settings.html')


@main_bp.route('/health')
def health():
    """نقطة فحص الصحة"""
    import logging
    import os
    from datetime import datetime

    from sqlalchemy import text as sa_text

    logger = logging.getLogger(__name__)

    db_status = 'connected'
    try:
        db.session.execute(sa_text('SELECT 1'))
    except Exception as e:
        db_status = 'error'
        logger.warning(f'Health check DB error: {e}')

    redis_status = 'connected'
    try:
        from app.core.rate_limiter import _get_redis

        _redis = _get_redis()
        if _redis:
            _redis.ping()
        else:
            redis_status = 'unavailable'
    except Exception as e:
        redis_status = 'error'
        logger.warning(f'Health check Redis error: {e}')

    # Stripe connectivity check
    stripe_status = 'unconfigured'
    try:
        import stripe

        stripe_key = os.environ.get('STRIPE_SECRET_KEY') or current_app.config.get(
            'STRIPE_SECRET_KEY'
        )
        if stripe_key:
            stripe.api_key = stripe_key
            stripe.Account.retrieve()
            stripe_status = 'connected'
        else:
            stripe_status = 'unconfigured'
    except Exception as e:
        stripe_status = 'error'
        logger.warning(f'Health check Stripe error: {e}')

    # Twilio/SMS connectivity check
    twilio_status = 'unconfigured'
    try:
        from app.integrations.sms.provider import get_sms_provider

        provider = get_sms_provider()
        if provider and hasattr(provider, 'check_connection'):
            twilio_status = 'connected' if provider.check_connection() else 'error'
        elif provider:
            twilio_status = 'connected'
        else:
            twilio_status = 'unconfigured'
    except Exception as e:
        twilio_status = 'error'
        logger.warning(f'Health check Twilio error: {e}')

    # SMTP connectivity check
    smtp_status = 'unconfigured'
    try:
        from flask import current_app

        mail_server = current_app.config.get('MAIL_SERVER')
        mail_port = current_app.config.get('MAIL_PORT')
        mail_username = current_app.config.get('MAIL_USERNAME')
        mail_password = current_app.config.get('MAIL_PASSWORD')
        if mail_server and mail_port and mail_username and mail_password:
            import smtplib

            with smtplib.SMTP(mail_server, mail_port, timeout=5) as server:
                if current_app.config.get('MAIL_USE_TLS'):
                    server.starttls()
                server.login(mail_username, mail_password)
            smtp_status = 'connected'
        else:
            smtp_status = 'unconfigured'
    except Exception as e:
        smtp_status = 'error'
        logger.warning(f'Health check SMTP error: {e}')

    overall = (
        'healthy'
        if all(
            s in ('connected', 'unconfigured', 'unavailable')
            for s in [db_status, redis_status, stripe_status, twilio_status, smtp_status]
        )
        and db_status == 'connected'
        else 'degraded'
    )

    payload = {
        'status': overall,
        'timestamp': datetime.now(UTC).isoformat(),
        'database': db_status,
        'redis': redis_status,
        'stripe': stripe_status,
        'twilio': twilio_status,
        'smtp': smtp_status,
        'version': '1.0.0',
    }

    status_code = 200 if overall == 'healthy' else 503
    return jsonify(payload), status_code


# تم نقل /change-password إلى auth_routes.py


@main_bp.route('/api/search')
@login_required
def api_search():
    """البحث في النظام"""
    return {'status': 'success', 'message': 'Search API working'}


@main_bp.route('/api/tenants/search')
def api_search_tenants():
    """البحث عن المستأجرين (Public - لا يتطلب تسجيل دخول)"""
    from app.core.tenant.models import Tenant
    from app.shared.enums import TenantStatus

    query = request.args.get('q', '').strip()
    if not query or len(query) < 2:
        return jsonify({'tenants': []})

    tenants = (
        db.session.execute(
            select(Tenant)
            .filter(
                Tenant.status.in_([TenantStatus.ACTIVE, TenantStatus.TRIAL]),
                db.or_(
                    Tenant.name.ilike(f'%{query}%'),
                    Tenant.name_ar.ilike(f'%{query}%'),
                    Tenant.slug.ilike(f'%{query}%'),
                ),
            )
            .limit(10)
        )
        .scalars()
        .all()
    )

    return jsonify(
        {
            'tenants': [
                {'id': t.id, 'name': t.name, 'name_ar': t.name_ar, 'slug': t.slug} for t in tenants
            ]
        }
    )


@main_bp.route('/privacy-policy')
def privacy_policy():
    """سياسة الخصوصية"""
    return render_template('main/privacy.html')


@main_bp.route('/terms-of-use')
def terms_of_use():
    """شروط الاستخدام"""
    return render_template('main/terms.html')


@main_bp.route('/technical-support')
def technical_support():
    """الدعم الفني"""
    return render_template('main/support.html')


@main_bp.route('/about-system')
def about_system():
    """حول النظام"""
    return render_template('main/about.html')
