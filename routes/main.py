"""
المسارات الرئيسية - Main Routes
Medical System Main Routes
"""

from flask import Blueprint, render_template, redirect, url_for, jsonify
from flask_login import login_required, current_user

main_bp = Blueprint('main', __name__)

@main_bp.get('/')
def index():
    """الصفحة الرئيسية — عرض المنصة والحزم"""
    if current_user.is_authenticated:
        if current_user.role == 'patient':
            return redirect(url_for('portal.dashboard'))
        return redirect(url_for('main.dashboard'))
    from app.core.tenant.models import ProductBundle
    bundles = ProductBundle.query.order_by(ProductBundle.id).all()
    # Group bundles by category for display
    cats = {
        'عيادات': ['private_doctor_clinic', 'doctor_clinic_reception', 'doctor_clinic_full', 'small_clinic', 'clinic_with_lab', 'clinic_with_radiology', 'clinic_with_lab_radiology', 'walkin_clinic'],
        'مختبرات وأشعة': ['standalone_lab', 'lab_with_reception', 'standalone_radiology', 'radiology_with_reception'],
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
    """لوحة التحكم الرئيسية - إعادة توجيه حسب الدور"""
    # إعادة التوجيه حسب دور المستخدم
    if current_user.role == 'super_admin':
        return redirect(url_for('super_admin.dashboard'))
    elif current_user.role == 'manager':
        return redirect(url_for('manager.dashboard'))
    elif current_user.role == 'reception':
        return redirect(url_for('reception.dashboard'))
    elif current_user.role == 'doctor':
        return redirect(url_for('doctor.dashboard'))
    elif current_user.role == 'emergency':
        return redirect(url_for('emergency.dashboard'))
    elif current_user.role == 'lab':
        return redirect(url_for('lab.dashboard'))
    elif current_user.role == 'radiology':
        return redirect(url_for('radiology.dashboard'))
    elif current_user.role == 'nurse':
        return redirect(url_for('nurse.dashboard'))
    elif current_user.role == 'accountant':
        return redirect(url_for('accountant.dashboard'))
    elif current_user.role == 'owner':
        return redirect(url_for('owner.owner_dashboard'))
    elif current_user.role == 'pharmacist':
        return redirect(url_for('medication.dashboard'))
    elif current_user.role == 'patient':
        return redirect(url_for('portal.dashboard'))
    elif current_user.role == 'technician':
        return redirect(url_for('lab.dashboard'))
    else:
        return redirect(url_for('auth.login'))

# تم نقل /profile إلى auth_routes.py

@main_bp.route('/appointments')
@login_required
def appointments_redirect():
    """إعادة توجيه المواعيد حسب الدور"""
    role = current_user.role
    if role == 'doctor':
        return redirect(url_for('doctor.appointments'))
    elif role == 'reception':
        return redirect(url_for('reception.appointments'))
    elif role == 'patient':
        return redirect(url_for('portal.appointments'))
    else:
        return redirect(url_for('reception.appointments'))

@main_bp.route('/settings')
@login_required
def settings():
    """الإعدادات"""
    return render_template('main/settings.html')

@main_bp.route('/health')
def health():
    """نقطة فحص الصحة"""
    from sqlalchemy import text as sa_text
    from app_factory import db
    from datetime import datetime, timezone
    
    try:
        # اختبار قاعدة البيانات
        db.session.execute(sa_text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = "error"
    
    payload = {
        "status": "healthy" if db_status == "connected" else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": db_status,
        "version": "1.0.0"
    }
    
    status_code = 200 if db_status == "connected" else 503
    return jsonify(payload), status_code

# تم نقل /change-password إلى auth_routes.py

@main_bp.route('/api/search')
@login_required
def api_search():
    """البحث في النظام"""
    return {'status': 'success', 'message': 'Search API working'}

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
