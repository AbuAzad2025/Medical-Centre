"""
المسارات الرئيسية - Main Routes
Medical System Main Routes
"""

from flask import Blueprint, render_template, redirect, url_for, jsonify
from flask_login import login_required, current_user

main_bp = Blueprint('main', __name__)

@main_bp.get('/')
def index():
    """الصفحة الرئيسية"""
    return redirect(url_for('auth.login'))

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
    else:
        return redirect(url_for('auth.login'))

# تم نقل /profile إلى auth_routes.py

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
