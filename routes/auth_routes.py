"""
مسارات المصادقة - Authentication Routes
Medical System Authentication Routes
"""

from flask import Blueprint, request, jsonify, session, redirect, url_for, flash, render_template
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf.csrf import generate_csrf, validate_csrf
from models.user import User
from models.permissions import Role
from werkzeug.security import check_password_hash
import logging

# إنشاء Blueprint للمصادقة
auth_bp = Blueprint('auth', __name__)

@auth_bp.get("/__ping")
def _auth_ping():
    return "auth ok", 200

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """تسجيل الدخول"""
    if request.method == 'GET':
        # عرض صفحة تسجيل الدخول
        return render_template('auth/login.html')
    
    if request.method == 'POST':
        try:
            # التحقق من CSRF token
            try:
                validate_csrf(request.form.get('csrf_token'))
            except Exception as csrf_error:
                logging.warning(f"CSRF validation failed: {csrf_error}")
                flash('خطأ في التحقق من الأمان. يرجى إعادة المحاولة.', 'error')
                return render_template('auth/login.html')
            
            # التحقق من نوع الطلب
            is_ajax = request.headers.get('Content-Type') == 'application/json' or request.is_json
            
            if is_ajax:
                data = request.get_json()
            else:
                data = request.form
            
            username = data.get('username')
            password = data.get('password')
            
            if not username or not password:
                if is_ajax:
                    return jsonify({
                        'success': False,
                        'message': 'اسم المستخدم وكلمة المرور مطلوبان'
                    }), 400
                else:
                    flash('اسم المستخدم وكلمة المرور مطلوبان', 'error')
                    return render_template('auth/login.html')
            
            # البحث عن المستخدم
            user = User.query.filter_by(username=username).first()
            logging.info(f"Login attempt for username: {username}. User found: {user is not None}")
            
            if user:
                password_check = user.check_password(password)
                logging.info(f"Password check for {username}: {password_check}")
                logging.info(f"User is_active: {user.is_active}")
            
            if user and user.check_password(password):
                if user.is_active:
                    login_user(user, remember=True)
                    logging.info(f"User {user.username} logged in successfully. Role: {user.role}")
                    
                    # تحديد الصفحة المناسبة حسب الدور
                    redirect_url = get_redirect_url_by_role(user.role)
                    logging.info(f"Redirecting to: {redirect_url}")
                    
                    if is_ajax:
                        return jsonify({
                            'success': True,
                            'message': 'تم تسجيل الدخول بنجاح',
                            'redirect_url': redirect_url,
                            'user': {
                                'id': user.id,
                                'username': user.username,
                                'full_name': user.full_name,
                                'role': user.role,
                                'department': user.department
                            }
                        })
                    else:
                        logging.info(f"Performing redirect to {redirect_url}")
                        return redirect(redirect_url)
                else:
                    if is_ajax:
                        return jsonify({
                            'success': False,
                            'message': 'حساب المستخدم غير مفعل'
                        }), 403
                    else:
                        flash('حساب المستخدم غير مفعل', 'error')
                        return render_template('auth/login.html')
            else:
                if is_ajax:
                    return jsonify({
                        'success': False,
                        'message': 'اسم المستخدم أو كلمة المرور غير صحيحة'
                    }), 401
                else:
                    flash('اسم المستخدم أو كلمة المرور غير صحيحة', 'error')
                    return render_template('auth/login.html')
                
        except Exception as e:
            logging.error(f"Login error: {str(e)}")
            if is_ajax:
                return jsonify({
                    'success': False,
                    'message': 'حدث خطأ في تسجيل الدخول'
                }), 500
            else:
                flash('حدث خطأ في تسجيل الدخول', 'error')
                return render_template('auth/login.html')
    
    # GET request - عرض صفحة تسجيل الدخول
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    """تسجيل الخروج"""
    logout_user()
    return redirect(url_for('auth.login'))

@auth_bp.route('/profile')
@login_required
def profile():
    """ملف المستخدم الشخصي"""
    return jsonify({
        'success': True,
        'user': {
            'id': current_user.id,
            'username': current_user.username,
            'full_name': current_user.full_name,
            'email': current_user.email,
            'phone': current_user.phone,
            'role': current_user.role,
            'department': current_user.department,
            'is_active': current_user.is_active,
            'created_at': current_user.created_at.isoformat()
        }
    })

@auth_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    """تغيير كلمة المرور"""
    try:
        data = request.get_json()
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        
        if not current_password or not new_password:
            return jsonify({
                'success': False,
                'message': 'كلمة المرور الحالية والجديدة مطلوبتان'
            }), 400
        
        # التحقق من كلمة المرور الحالية
        if not check_password_hash(current_user.password_hash, current_password):
            return jsonify({
                'success': False,
                'message': 'كلمة المرور الحالية غير صحيحة'
            }), 400
        
        # تحديث كلمة المرور
        from werkzeug.security import generate_password_hash
        current_user.password_hash = generate_password_hash(new_password)
        from app_factory import db
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'تم تغيير كلمة المرور بنجاح'
        })
        
    except Exception as e:
        logging.error(f"Change password error: {str(e)}")
        return jsonify({
            'success': False,
            'message': 'حدث خطأ في تغيير كلمة المرور'
        }), 500

def get_redirect_url_by_role(role):
    """تحديد الصفحة المناسبة حسب الدور"""
    from services.access_control_service import AccessControlService
    
    # استخدام خدمة التحكم في الوصول للحصول على المسار الصحيح
    role_urls = {
        'super_admin': '/super-admin/dashboard',
        'admin': '/super-admin/dashboard',  # إضافة admin
        'manager': '/manager/dashboard',
        'reception': '/reception/dashboard',
        'doctor': '/doctor/dashboard',
        'radiology': '/radiology/dashboard',
        'lab': '/lab/dashboard',
        'emergency': '/emergency/dashboard',
        'nurse': '/nurse/dashboard',
        'accountant': '/accountant/dashboard',
        'medication': '/medication/dashboard'  # إضافة medication
    }
    return role_urls.get(role, '/super-admin/dashboard')
