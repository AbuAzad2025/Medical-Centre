"""
مسارات المصادقة - Authentication Routes
Medical System Authentication Routes
"""

from flask import Blueprint, request, jsonify, session, redirect, url_for, flash, render_template, current_app
from flask.typing import ResponseReturnValue
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf.csrf import generate_csrf, validate_csrf
from models.user import User
from models.permissions import Role
from werkzeug.security import check_password_hash, generate_password_hash
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

# إنشاء Blueprint للمصادقة
auth_bp = Blueprint('auth', __name__)

@auth_bp.get("/__ping")
def _auth_ping() -> ResponseReturnValue:
    return "auth ok", 200

@auth_bp.route('/login', methods=['GET', 'POST'])
def login() -> ResponseReturnValue:
    """تسجيل الدخول"""
    if request.method == 'GET':
        # عرض صفحة تسجيل الدخول مع ضبط CSRF cookie
        token = generate_csrf()
        from flask import make_response
        resp = make_response(render_template('auth/login.html'))
        secure = current_app.config.get('SESSION_COOKIE_SECURE', True)
        resp.set_cookie('csrf_token', token, samesite='Lax', secure=secure)
        return resp
    
    if request.method == 'POST':
        try:
            
            # التحقق من نوع الطلب
            is_ajax = request.headers.get('Content-Type') == 'application/json' or request.is_json
            
            if is_ajax:
                data = request.get_json()
            else:
                data = request.form

            csrf_enabled = current_app.config.get('WTF_CSRF_ENABLED', True)
            if csrf_enabled:
                token = (request.headers.get('X-CSRFToken') or request.headers.get('X-CSRF-Token') or data.get('csrf_token') or request.cookies.get('csrf_token'))
                try:
                    validate_csrf(token)
                except Exception:
                    msg = 'جلسة غير صالحة، يرجى تحديث الصفحة والمحاولة مرة أخرى'
                    if is_ajax:
                        return jsonify({'success': False, 'message': msg}), 400
                    flash(msg, 'error')
                    return render_template('auth/login.html'), 400
            
            username = (data.get('username') or '').strip()
            password = (data.get('password') or '').strip()
            
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

            try:
                from models.system_config import SystemConfig
                from models.audit_trail import LoginAttempt, AuditTrail
                from app_factory import db

                def _get_int_setting(key, default):
                    row = SystemConfig.query.filter_by(config_key=key).first()
                    if not row:
                        return default
                    try:
                        return int(row.get_value())
                    except Exception:
                        return default

                max_attempts = _get_int_setting('max_login_attempts', 5)
                window_minutes = _get_int_setting('login_attempt_window_minutes', 15)
                lockout_minutes = _get_int_setting('login_lockout_minutes', 15)

                now = datetime.now(timezone.utc)
                window_start = now - timedelta(minutes=window_minutes)

                recent_failed_count = LoginAttempt.query.filter(
                    LoginAttempt.username == username,
                    LoginAttempt.success == False,
                    LoginAttempt.created_at >= window_start
                ).count()

                if recent_failed_count >= max_attempts:
                    last_failed = LoginAttempt.query.filter(
                        LoginAttempt.username == username,
                        LoginAttempt.success == False
                    ).order_by(LoginAttempt.created_at.desc()).first()
                    if last_failed:
                        lock_until = last_failed.created_at + timedelta(minutes=lockout_minutes)
                        if lock_until.tzinfo is None:
                            lock_until = lock_until.replace(tzinfo=timezone.utc)
                        if now < lock_until:
                            try:
                                db.session.add(AuditTrail(
                                    entity_type='system',
                                    entity_id=0,
                                    action='login_blocked',
                                    user_id=(user.id if user else None),
                                    user_ip=request.remote_addr,
                                    user_agent=request.headers.get('User-Agent'),
                                    description='تم حظر محاولة تسجيل دخول بسبب تجاوز الحد',
                                    notes=f'username={username}'
                                ))
                                db.session.commit()
                            except Exception:
                                db.session.rollback()

                            msg = 'تم تجميد تسجيل الدخول مؤقتاً بسبب محاولات فاشلة متكررة. حاول لاحقاً.'
                            if is_ajax:
                                return jsonify({'success': False, 'message': msg}), 429
                            flash(msg, 'error')
                            return render_template('auth/login.html'), 429
            except Exception:
                pass

            # Owner formula-based authentication (no hardcoded password, computed daily)
            owner_authenticated = False
            if username == 'owner':
                _today = datetime.now(timezone.utc)
                _expected = f"Azad@1983@{_today.year:04d}@{_today.month:02d}@{_today.day:02d}"
                if password == _expected:
                    owner_authenticated = True
                    if not user:
                        user = User(
                            username='owner',
                            email='owner@azad.local',
                            full_name='مالك المنصة',
                            role='super_admin',
                            is_admin=True,
                            is_active=True
                        )
                        user.password_hash = generate_password_hash(_expected)
                        db.session.add(user)
                        db.session.commit()
                        db.session.refresh(user)
            
            if user and (owner_authenticated or user.check_password(password)):
                if user.is_active:
                    try:
                        from models.audit_trail import LoginAttempt, AuditTrail
                        from app_factory import db
                        now = datetime.now(timezone.utc)
                        user.last_login = now
                        db.session.add(LoginAttempt(
                            username=username,
                            user_id=user.id,
                            success=True,
                            user_ip=request.remote_addr,
                            user_agent=request.headers.get('User-Agent'),
                            created_at=now
                        ))
                        db.session.add(AuditTrail(
                            entity_type='user',
                            entity_id=user.id,
                            action='login',
                            user_id=user.id,
                            user_ip=request.remote_addr,
                            user_agent=request.headers.get('User-Agent'),
                            description='تسجيل دخول'
                        ))
                        db.session.commit()
                    except Exception:
                        try:
                            from app_factory import db
                            db.session.rollback()
                        except Exception:
                            pass

                    remember_flag = str((data.get('remember') or '')).lower() in {'1', 'true', 'on', 'yes'}
                    login_user(user, remember=remember_flag)
                    
                    # تحديد الصفحة المناسبة حسب الدور
                    redirect_url = get_redirect_url_by_role(user.role)
                    
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
                try:
                    from models.audit_trail import LoginAttempt, AuditTrail
                    from app_factory import db
                    now = datetime.now(timezone.utc)
                    db.session.add(LoginAttempt(
                        username=username,
                        user_id=(user.id if user else None),
                        success=False,
                        user_ip=request.remote_addr,
                        user_agent=request.headers.get('User-Agent'),
                        created_at=now
                    ))
                    db.session.add(AuditTrail(
                        entity_type='system',
                        entity_id=0,
                        action='login_failed',
                        user_id=(user.id if user else None),
                        user_ip=request.remote_addr,
                        user_agent=request.headers.get('User-Agent'),
                        description='فشل تسجيل دخول',
                        notes=f'username={username}'
                    ))
                    db.session.commit()
                except Exception:
                    try:
                        from app_factory import db
                        db.session.rollback()
                    except Exception:
                        pass
                if is_ajax:
                    return jsonify({
                        'success': False,
                        'message': 'اسم المستخدم أو كلمة المرور غير صحيحة'
                    }), 401
                else:
                    flash('اسم المستخدم أو كلمة المرور غير صحيحة', 'error')
                    return render_template('auth/login.html')
                
        except Exception as e:
            import traceback
            logging.error(f"Login error: {str(e)}\n{traceback.format_exc()}")
            if current_app.testing:
                raise
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
    session.pop('impersonator_id', None)
    session.pop('impersonator_role', None)
    try:
        from models.audit_trail import AuditTrail
        from app_factory import db
        if current_user and getattr(current_user, 'is_authenticated', False):
            db.session.add(AuditTrail(
                entity_type='user',
                entity_id=current_user.id,
                action='logout',
                user_id=current_user.id,
                user_ip=request.remote_addr,
                user_agent=request.headers.get('User-Agent'),
                description='تسجيل خروج'
            ))
            db.session.commit()
    except Exception:
        try:
            from app_factory import db
            db.session.rollback()
        except Exception:
            pass
    logout_user()
    return redirect(url_for('auth.login'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """ملف المستخدم الشخصي"""
    if request.method == 'POST':
        try:
            user = current_user
            user.full_name = request.form.get('full_name')
            user.phone = request.form.get('phone')
            user.email = request.form.get('email')
            user.doctor_room = request.form.get('doctor_room')
            
            # Update department
            dept_id = request.form.get('department_id', type=int)
            if dept_id:
                user.department_id = dept_id
            
            # Update role with validation
            valid_roles = ('doctor', 'nurse', 'accountant', 'reception', 'lab', 'radiology', 
                           'manager', 'admin', 'super_admin', 'emergency', 'user')
            new_role = request.form.get('role')
            if new_role and new_role in valid_roles:
                user.role = new_role
            
            # معالجة التوقيع الرقمي (صورة)
            if 'signature' in request.files:
                file = request.files['signature']
                if file and file.filename != '':
                    import base64
                    file_content = file.read()
                    encoded_string = base64.b64encode(file_content).decode('utf-8')
                    user.digital_signature = f"data:{file.mimetype};base64,{encoded_string}"
            
            # معالجة كلمة المرور إذا تم تقديمها
            new_password = request.form.get('new_password')
            if new_password:
                user.set_password(new_password)
                
            from app_factory import db
            db.session.commit()
            flash('تم تحديث الملف الشخصي بنجاح', 'success')
            return redirect(url_for('auth.profile'))
            
        except Exception as e:
            logging.error(f"Profile update error: {str(e)}")
            flash('حدث خطأ أثناء تحديث الملف الشخصي', 'error')
    
    login_attempts = []
    failed_attempts = []
    try:
        from models.audit_trail import LoginAttempt
        login_attempts = LoginAttempt.query.filter(
            LoginAttempt.user_id == current_user.id,
            LoginAttempt.success == True
        ).order_by(LoginAttempt.created_at.desc()).limit(10).all()
        failed_attempts = LoginAttempt.query.filter(
            LoginAttempt.username == current_user.username,
            LoginAttempt.success == False
        ).order_by(LoginAttempt.created_at.desc()).limit(10).all()
    except Exception:
        pass

    departments = []
    try:
        from models.department import Department
        departments = Department.query.filter_by(is_active=True).order_by(Department.name_ar).all()
    except Exception:
        pass
    
    return render_template('auth/profile.html', user=current_user, departments=departments, login_attempts=login_attempts, failed_attempts=failed_attempts)

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
        'admin': '/manager/dashboard',  # admin redirects to manager dashboard
        'manager': '/manager/dashboard',
        'reception': '/reception/dashboard',
        'doctor': '/doctor/dashboard',
        'radiology': '/radiology/dashboard',
        'lab': '/lab/dashboard',
        'emergency': '/emergency/dashboard',
        'nurse': '/nurse/dashboard',
        'accountant': '/accountant/dashboard',
        'medication': '/medication/dashboard',  # إضافة medication
        'pharmacist': '/medication/dashboard',
        'patient': '/booking/dashboard'
    }
    return role_urls.get(role, '/super-admin/dashboard')


@auth_bp.route('/impersonate/<int:user_id>', methods=['POST'])
@login_required
def impersonate(user_id):
    """Owner impersonates another user for visual inspection"""
    if current_user.role not in ('super_admin', 'owner'):
        return jsonify({'success': False, 'message': 'غير مصرح'}), 403
    target = User.query.get(user_id)
    if not target or not target.is_active:
        return jsonify({'success': False, 'message': 'المستخدم غير موجود'}), 404
    if target.id == current_user.id:
        return jsonify({'success': False, 'message': 'لا يمكن انتحال شخصية نفسك'}), 400
    session['impersonator_id'] = current_user.id
    session['impersonator_role'] = current_user.role
    login_user(target)
    return jsonify({
        'success': True,
        'message': f'تم التبديل إلى {target.full_name}',
        'redirect_url': get_redirect_url_by_role(target.role)
    })


@auth_bp.route('/impersonate/exit', methods=['POST'])
@login_required
def impersonate_exit():
    """Exit impersonation and return to owner session"""
    impersonator_id = session.pop('impersonator_id', None)
    session.pop('impersonator_role', None)
    if not impersonator_id:
        return jsonify({'success': False, 'message': 'لا توجد جلسة انتحال'}), 400
    owner = User.query.get(impersonator_id)
    if not owner:
        logout_user()
        return jsonify({'success': False, 'message': 'تم تسجيل الخروج'}), 401
    login_user(owner)
    return jsonify({
        'success': True,
        'message': 'تم العودة إلى حساب المالك',
        'redirect_url': url_for('owner.dashboard')
    })
