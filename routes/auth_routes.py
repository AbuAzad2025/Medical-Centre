"""
مسارات المصادقة - Authentication Routes
Medical System Authentication Routes
"""

import contextlib
import logging
import secrets
from datetime import UTC, datetime, timedelta

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf.csrf import generate_csrf, validate_csrf
from sqlalchemy import func, select
from werkzeug.security import check_password_hash, generate_password_hash

from app.core.rate_limiter import rate_limit
from app.extensions import db
from models.user import User
from utils.db_safety import safe_commit, safe_rollback
from utils.decorators import role_required_json

# إنشاء Blueprint للمصادقة
auth_bp = Blueprint('auth', __name__)


@auth_bp.context_processor
def _inject_saas_enabled():
    """Expose whether SaaS tenant selection is active to the login template."""
    return {'saas_enabled': current_app.config.get('ENABLE_SAAS_MODE', False)}


@auth_bp.route('/api/tenants-list')
def api_tenants_list():
    """
    إرجاع قائمة التينانتس النشطة لاختيار المنشأة في صفحة الدخول.
    يستخدمها Owner/SuperAdmin فقط، أو عند الدخول بدون سياق تينانت.
    """
    try:
        from app.core.tenant.models import Tenant
        from app.shared.enums import TenantStatus

        tenants = (
            db.session.execute(
                select(Tenant)
                .filter(
                    Tenant.status.in_(
                        (TenantStatus.ACTIVE, TenantStatus.TRIAL, TenantStatus.PENDING)
                    )
                )
                .order_by(Tenant.name_ar, Tenant.name)
            )
            .scalars()
            .all()
        )
        return jsonify(
            {
                'tenants': [
                    {'id': t.id, 'slug': t.slug, 'name': t.name_ar or t.name} for t in tenants
                ]
            }
        )
    except Exception:
        return jsonify({'tenants': []})


@auth_bp.route('/login', methods=['GET', 'POST'])
# 30 POSTs/min/IP: clinics behind one NAT legitimately exceed 10 logins/min
# during morning shift. Brute-force defense-in-depth remains the per-username
# LoginAttempt lockout (5 failures -> temporary lock) enforced below.
@rate_limit(max_requests=30, window_seconds=60, namespace='auth')
def login() -> ResponseReturnValue:
    """تسجيل الدخول"""
    if request.method == 'GET':
        # عرض صفحة تسجيل الدخول مع ضبط CSRF cookie
        mode = request.args.get('mode', '')
        token = generate_csrf()
        from flask import make_response

        resp = make_response(render_template('auth/login.html', mode=mode))
        secure = current_app.config.get('SESSION_COOKIE_SECURE', True)
        resp.set_cookie('csrf_token', token, samesite='Lax', secure=secure)
        return resp

    if request.method == 'POST':
        try:
            # التحقق من نوع الطلب
            is_ajax = request.headers.get('Content-Type') == 'application/json' or request.is_json

            data = request.get_json() if is_ajax else request.form

            csrf_enabled = current_app.config.get('WTF_CSRF_ENABLED', True)
            if csrf_enabled:
                token = (
                    request.headers.get('X-CSRFToken')
                    or request.headers.get('X-CSRF-Token')
                    or data.get('csrf_token')
                    or request.cookies.get('csrf_token')
                )
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
            login_mode = (data.get('mode') or '').strip()

            if not username or not password:
                if is_ajax:
                    return jsonify(
                        {'success': False, 'message': 'اسم المستخدم وكلمة المرور مطلوبان'}
                    ), 400
                flash('اسم المستخدم وكلمة المرور مطلوبان', 'error')
                return render_template('auth/login.html')

            # SaaS: bind tenant from slug before tenant-scoped User lookup
            tenant_slug = (data.get('tenant_slug') or '').strip()
            if current_app.config.get('ENABLE_SAAS_MODE', False):
                from flask import g

                from app.core.tenant.middleware import _get_tenant_by_slug, bind_g_tenant

                if tenant_slug:
                    _login_tenant = _get_tenant_by_slug(tenant_slug)
                    if _login_tenant:
                        bind_g_tenant(_login_tenant)
                else:
                    # Platform owner / super-admin may authenticate without a tenant slug
                    g._tenant_filter_bypass = True

            # البحث عن المستخدم
            user = db.session.execute(select(User).filter_by(username=username)).scalars().first()

            try:
                from models.audit_trail import AuditTrail, LoginAttempt
                from models.system_config import SystemConfig

                def _get_int_setting(key, default):
                    row = (
                        db.session.execute(select(SystemConfig).filter_by(config_key=key))
                        .scalars()
                        .first()
                    )
                    if not row:
                        return default
                    try:
                        return int(row.get_value())
                    except Exception:
                        return default

                max_attempts = _get_int_setting('max_login_attempts', 5)
                window_minutes = _get_int_setting('login_attempt_window_minutes', 15)
                lockout_minutes = _get_int_setting('login_lockout_minutes', 15)

                now = datetime.now(UTC)
                window_start = now - timedelta(minutes=window_minutes)

                recent_failed_count = db.session.execute(
                    select(func.count())
                    .select_from(LoginAttempt)
                    .filter(
                        LoginAttempt.username == username,
                        ~LoginAttempt.success,
                        LoginAttempt.created_at >= window_start,
                    )
                ).scalar()

                if recent_failed_count >= max_attempts:
                    last_failed = (
                        db.session.execute(
                            select(LoginAttempt)
                            .filter(LoginAttempt.username == username, ~LoginAttempt.success)
                            .order_by(LoginAttempt.created_at.desc())
                        )
                        .scalars()
                        .first()
                    )
                    if last_failed:
                        lock_until = last_failed.created_at + timedelta(minutes=lockout_minutes)
                        if lock_until.tzinfo is None:
                            lock_until = lock_until.replace(tzinfo=UTC)
                        if now < lock_until:
                            try:
                                db.session.add(
                                    AuditTrail(
                                        entity_type='system',
                                        entity_id=0,
                                        action='login_blocked',
                                        user_id=(user.id if user else None),
                                        user_ip=request.remote_addr,
                                        user_agent=request.headers.get('User-Agent'),
                                        description='تم حظر محاولة تسجيل دخول بسبب تجاوز الحد',
                                        notes=f'username={username}',
                                    )
                                )
                                safe_commit(
                                    db.session, error_message='database commit failed', reraise=True
                                )
                            except Exception:
                                safe_rollback(db.session, error_message='database rollback')

                            msg = (
                                'تم تجميد تسجيل الدخول مؤقتاً بسبب محاولات فاشلة متكررة. حاول لاحقاً.'
                            )
                            if is_ajax:
                                return jsonify({'success': False, 'message': msg}), 429
                            flash(msg, 'error')
                            return render_template('auth/login.html'), 429
            except Exception as e:
                logging.warning(f'Error in {__name__}: {e}')

            if user and user.check_password(password):
                if user.is_active:
                    from flask import g as _login_g

                    from app.shared.enums import TenantStatus

                    bound_tenant = getattr(_login_g, 'current_tenant', None)
                    if bound_tenant and bound_tenant.status not in (
                        TenantStatus.ACTIVE,
                        TenantStatus.TRIAL,
                        TenantStatus.PENDING,
                    ):
                        msg = 'الاشتراك موقوف أو منتهٍ. تواصل مع إدارة المنصة.'
                        if is_ajax:
                            return jsonify({'success': False, 'message': msg}), 403
                        flash(msg, 'error')
                        return render_template('auth/login.html'), 403
                    try:
                        from models.audit_trail import AuditTrail, LoginAttempt

                        now = datetime.now(UTC)
                        user.last_login = now
                        db.session.add(
                            LoginAttempt(
                                username=username,
                                user_id=user.id,
                                tenant_id=user.tenant_id,
                                success=True,
                                user_ip=request.remote_addr,
                                user_agent=request.headers.get('User-Agent'),
                                created_at=now,
                            )
                        )
                        db.session.add(
                            AuditTrail(
                                entity_type='user',
                                entity_id=user.id,
                                tenant_id=user.tenant_id,
                                action='login',
                                user_id=user.id,
                                user_ip=request.remote_addr,
                                user_agent=request.headers.get('User-Agent'),
                                description='تسجيل دخول',
                            )
                        )
                        safe_commit(
                            db.session, error_message='database commit failed', reraise=True
                        )
                    except Exception:
                        try:
                            safe_rollback(db.session, error_message='database rollback')
                        except Exception as e:
                            logging.warning(f'Error in {__name__}: {e}')
                    # Session logging + concurrent session limit
                    try:
                        import hashlib

                        from models.digital_signature import SessionLog

                        fingerprint = hashlib.sha256(
                            (request.headers.get('User-Agent', '') + request.remote_addr).encode()
                        ).hexdigest()[:16]
                        max_sessions = 3
                        active = (
                            db.session.execute(
                                select(SessionLog).filter_by(
                                    user_id=user.id, is_active=True, tenant_id=user.tenant_id
                                )
                            )
                            .scalars()
                            .all()
                        )
                        if len(active) >= max_sessions:
                            oldest = sorted(active, key=lambda s: s.login_at or '')[0]
                            oldest.is_active = False
                            oldest.terminated_by = 'SYSTEM_LIMIT'
                        new_session = SessionLog(
                            user_id=user.id,
                            tenant_id=user.tenant_id,
                            session_id=session.sid if hasattr(session, 'sid') else '__main__',
                            ip_address=request.remote_addr,
                            user_agent=request.headers.get('User-Agent'),
                            device_type='DESKTOP',
                            browser='Unknown',
                            os='Unknown',
                            fingerprint=fingerprint,
                            is_active=True,
                            login_at=datetime.now(UTC),
                        )
                        db.session.add(new_session)
                        safe_commit(
                            db.session, error_message='database commit failed', reraise=True
                        )
                    except Exception as e:
                        with contextlib.suppress(Exception):
                            safe_rollback(db.session, error_message='database rollback')
                        logging.warning(f'Session log error: {e}')
                    remember_flag = str(data.get('remember') or '').lower() in {
                        '1',
                        'true',
                        'on',
                        'yes',
                    }
                    login_user(user, remember=remember_flag)

                    from flask import g as _g

                    session['tenant_id'] = user.tenant_id or getattr(_g, 'tenant_id', None)
                    if tenant_slug:
                        session['tenant_slug'] = tenant_slug
                    elif getattr(_g, 'tenant_slug', None):
                        session['tenant_slug'] = _g.tenant_slug

                    # تحديد الصفحة المناسبة حسب الدور والحزمة النشطة (Strict Role + Bundle Scoped)
                    from services.dashboard_routing import resolve_dashboard_for_user

                    redirect_url = url_for(resolve_dashboard_for_user(user))

                    # Owner mode: always redirect platform owners to owner dashboard
                    if login_mode == 'owner' and user.role in (
                        'super_admin',
                        'owner',
                        'platform_owner',
                    ):
                        redirect_url = url_for('owner.owner_dashboard')

                    # handle tenant_slug for multi-tenant SaaS (may already be set above)
                    if not tenant_slug and user.tenant_id:
                        try:
                            from app.core.tenant.models import Tenant

                            t = db.session.get(Tenant, user.tenant_id)
                            if t:
                                tenant_slug = t.slug
                        except Exception:
                            pass
                    # Do not prepend /t/{slug} for platform owners logging into owner mode
                    if tenant_slug and login_mode != 'owner':
                        from app.core.tenant.models import Tenant

                        t = (
                            db.session.execute(select(Tenant).filter_by(slug=tenant_slug))
                            .scalars()
                            .first()
                        )
                        if t and (not user.tenant_id or user.tenant_id == t.id):
                            redirect_url = f'/t/{tenant_slug}{redirect_url}'

                    if is_ajax:
                        return jsonify(
                            {
                                'success': True,
                                'message': 'تم تسجيل الدخول بنجاح',
                                'redirect_url': redirect_url,
                                'user': {
                                    'id': user.id,
                                    'username': user.username,
                                    'full_name': user.full_name,
                                    'role': user.role,
                                    'department': user.department,
                                    'tenant_slug': tenant_slug,
                                },
                            }
                        )
                    return redirect(redirect_url)
                if is_ajax:
                    return jsonify({'success': False, 'message': 'حساب المستخدم غير مفعل'}), 403
                flash('حساب المستخدم غير مفعل', 'error')
                return render_template('auth/login.html')
            try:
                from models.audit_trail import AuditTrail, LoginAttempt

                now = datetime.now(UTC)
                # Both tables have NOT NULL tenant_id in the live schema, so
                # rows are only persisted when a user (and thus tenant) is
                # known. Unknown-username attempts raise inside safe_commit
                # and are swallowed by the handler below.
                if user is not None:
                    db.session.add(
                        LoginAttempt(
                            username=username,
                            user_id=user.id,
                            tenant_id=user.tenant_id,
                            success=False,
                            user_ip=request.remote_addr,
                            user_agent=request.headers.get('User-Agent'),
                            created_at=now,
                        )
                    )
                    db.session.add(
                        AuditTrail(
                            entity_type='system',
                            entity_id=0,
                            tenant_id=user.tenant_id,
                            action='login_failed',
                            user_id=user.id,
                            user_ip=request.remote_addr,
                            user_agent=request.headers.get('User-Agent'),
                            description='فشل تسجيل دخول',
                            notes=f'username={username}',
                        )
                    )
                    safe_commit(db.session, error_message='database commit failed', reraise=True)
            except Exception:
                try:
                    safe_rollback(db.session, error_message='database rollback')
                except Exception as e:
                    logging.warning(f'Error in {__name__}: {e}')
            if is_ajax:
                return jsonify(
                    {'success': False, 'message': 'اسم المستخدم أو كلمة المرور غير صحيحة'}
                ), 401
            flash('اسم المستخدم أو كلمة المرور غير صحيحة', 'error')
            return render_template('auth/login.html')

        except Exception:
            logging.exception('Login error')
            if current_app.testing:
                raise
            if is_ajax:
                return jsonify({'success': False, 'message': 'حدث خطأ في تسجيل الدخول'}), 500
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
    session.pop('tenant_id', None)
    session.pop('tenant_slug', None)
    try:
        from models.audit_trail import AuditTrail

        if current_user and getattr(current_user, 'is_authenticated', False):
            db.session.add(
                AuditTrail(
                    entity_type='user',
                    entity_id=current_user.id,
                    action='logout',
                    user_id=current_user.id,
                    user_ip=request.remote_addr,
                    user_agent=request.headers.get('User-Agent'),
                    description='تسجيل خروج',
                )
            )
            safe_commit(db.session, error_message='database commit failed', reraise=True)
    except Exception:
        try:
            safe_rollback(db.session, error_message='database rollback')
        except Exception as e:
            logging.warning(f'Error in {__name__}: {e}')
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

            # Role is immutable via self-service profile (P0 — no self-privilege escalation).
            if request.form.get('role'):
                logging.warning(
                    'Rejected self-service role change attempt user_id=%s role=%s',
                    current_user.id,
                    request.form.get('role'),
                )

            # معالجة التوقيع الرقمي (صورة)
            if 'signature' in request.files:
                file = request.files['signature']
                if file and file.filename != '':
                    import base64

                    file_content = file.read()
                    encoded_string = base64.b64encode(file_content).decode('utf-8')
                    user.digital_signature = f'data:{file.mimetype};base64,{encoded_string}'

            # معالجة كلمة المرور إذا تم تقديمها
            new_password = request.form.get('new_password')
            if new_password:
                user.set_password(new_password)

            safe_commit(db.session, error_message='database commit failed', reraise=True)
            flash('تم تحديث الملف الشخصي بنجاح', 'success')
            return redirect(url_for('auth.profile'))

        except Exception:
            logging.exception('Profile update error')
            flash('حدث خطأ أثناء تحديث الملف الشخصي', 'error')

    login_attempts = []
    failed_attempts = []
    try:
        from models.audit_trail import LoginAttempt

        login_attempts = (
            db.session.execute(
                select(LoginAttempt)
                .filter(LoginAttempt.user_id == current_user.id, LoginAttempt.success)
                .order_by(LoginAttempt.created_at.desc())
                .limit(10)
            )
            .scalars()
            .all()
        )
        failed_attempts = (
            db.session.execute(
                select(LoginAttempt)
                .filter(LoginAttempt.username == current_user.username, ~LoginAttempt.success)
                .order_by(LoginAttempt.created_at.desc())
                .limit(10)
            )
            .scalars()
            .all()
        )
    except Exception as e:
        logging.warning(f'Error in {__name__}: {e}')
    departments = []
    try:
        from models.department import Department

        departments = (
            db.session.execute(
                select(Department).filter_by(is_active=True).order_by(Department.name_ar)
            )
            .scalars()
            .all()
        )
    except Exception as e:
        logging.warning(f'Error in {__name__}: {e}')
    return render_template(
        'auth/profile.html',
        user=current_user,
        departments=departments,
        login_attempts=login_attempts,
        failed_attempts=failed_attempts,
    )


@auth_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    """تغيير كلمة المرور"""
    try:
        data = request.get_json()
        current_password = data.get('current_password')
        new_password = data.get('new_password')

        if not current_password or not new_password:
            return jsonify(
                {'success': False, 'message': 'كلمة المرور الحالية والجديدة مطلوبتان'}
            ), 400

        # التحقق من كلمة المرور الحالية
        if not check_password_hash(current_user.password_hash, current_password):
            return jsonify({'success': False, 'message': 'كلمة المرور الحالية غير صحيحة'}), 400

        # تحديث كلمة المرور
        current_user.password_hash = generate_password_hash(new_password)
        current_user.session_version = (current_user.session_version or 0) + 1
        safe_commit(db.session, error_message='database commit failed', reraise=True)

        return jsonify({'success': True, 'message': 'تم تغيير كلمة المرور بنجاح'})

    except Exception:
        logging.exception('Change password error')
        return jsonify({'success': False, 'message': 'حدث خطأ في تغيير كلمة المرور'}), 500


# =============================================
# PASSWORD RESET (FORGOT PASSWORD) FLOW
# =============================================


def _generate_reset_token() -> str:
    """Generate a secure password reset token."""
    return secrets.token_urlsafe(32)


def _store_reset_token(user_id: int, token: str, expires_at: datetime) -> None:
    """Store password reset token in user preferences JSON."""
    user = db.session.get(User, user_id)
    if not user:
        return
    prefs = user.preferences or {}
    prefs['password_reset_token'] = token
    prefs['password_reset_expires'] = expires_at.isoformat()
    user.preferences = prefs
    safe_commit(db.session, error_message='database commit failed', reraise=True)


def _verify_reset_token(user_id: int, token: str) -> bool:
    """Verify password reset token."""
    user = db.session.get(User, user_id)
    if not user or not user.preferences:
        return False
    stored_token = user.preferences.get('password_reset_token')
    expires_str = user.preferences.get('password_reset_expires')
    if not stored_token or not expires_str:
        return False
    if stored_token != token:
        return False
    try:
        expires_at = datetime.fromisoformat(expires_str)
        if datetime.now(UTC) > expires_at:
            return False
    except Exception:
        return False
    return True


def _clear_reset_token(user_id: int) -> None:
    """Clear password reset token after use."""
    user = db.session.get(User, user_id)
    if not user or not user.preferences:
        return
    prefs = user.preferences
    prefs.pop('password_reset_token', None)
    prefs.pop('password_reset_expires', None)
    user.preferences = prefs
    safe_commit(db.session, error_message='database commit failed', reraise=True)


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
@rate_limit(max_requests=3, window_seconds=3600, namespace='auth')
def forgot_password() -> ResponseReturnValue:
    """طلب إعادة تعيين كلمة المرور - يرسل رمزاً بالبريد الإلكتروني أو واتساب"""
    if request.method == 'GET':
        token = generate_csrf()
        from flask import make_response

        resp = make_response(render_template('auth/forgot_password.html'))
        secure = current_app.config.get('SESSION_COOKIE_SECURE', True)
        resp.set_cookie('csrf_token', token, samesite='Lax', secure=secure)
        return resp

    # POST - Process forgot password request
    try:
        is_ajax = request.headers.get('Content-Type') == 'application/json' or request.is_json
        data = request.get_json() if is_ajax else request.form

        # CSRF validation
        csrf_enabled = current_app.config.get('WTF_CSRF_ENABLED', True)
        if csrf_enabled:
            token = (
                request.headers.get('X-CSRFToken')
                or request.headers.get('X-CSRF-Token')
                or data.get('csrf_token')
                or request.cookies.get('csrf_token')
            )
            try:
                validate_csrf(token)
            except Exception:
                msg = 'جلسة غير صالحة، يرجى تحديث الصفحة والمحاولة مرة أخرى'
                if is_ajax:
                    return jsonify({'success': False, 'message': msg}), 400
                flash(msg, 'error')
                return render_template('auth/forgot_password.html'), 400

        identifier = (data.get('identifier') or '').strip()  # username or email
        if not identifier:
            msg = 'اسم المستخدم أو البريد الإلكتروني مطلوب'
            if is_ajax:
                return jsonify({'success': False, 'message': msg}), 400
            flash(msg, 'error')
            return render_template('auth/forgot_password.html')

        # Find user by username or email
        user = (
            db.session.execute(
                select(User).filter((User.username == identifier) | (User.email == identifier))
            )
            .scalars()
            .first()
        )

        # Always return success to prevent user enumeration
        success_msg = 'إذا كان الحساب موجوداً، سيتم إرسال رابط إعادة تعيين كلمة المرور'

        if user and user.is_active:
            # Generate reset token (valid for 1 hour)
            reset_token = _generate_reset_token()
            expires_at = datetime.now(UTC) + timedelta(hours=1)
            _store_reset_token(user.id, reset_token, expires_at)

            # Send reset link via email
            reset_url = url_for(
                'auth.reset_password', token=reset_token, user_id=user.id, _external=True
            )

            try:
                from flask_mail import Message

                from app.extensions import mail

                msg = Message(
                    subject='إعادة تعيين كلمة المرور - نظام الإدارة الطبية',
                    recipients=[user.email],
                    html=render_template(
                        'emails/password_reset.html',
                        user=user,
                        reset_url=reset_url,
                        expires_hours=1,
                    ),
                )
                mail.send(msg)
                logging.info(f'Password reset email sent to user {user.id}')
            except Exception as e:
                logging.warning(f'Failed to send password reset email: {e}')
                # Try WhatsApp as fallback
                try:
                    from app.integrations.whatsapp.service import WhatsAppService

                    whatsapp = WhatsAppService()
                    whatsapp.send_message(
                        to=user.phone,
                        body=f'رابط إعادة تعيين كلمة المرور: {reset_url} (صالح لساعة واحدة)',
                    )
                except Exception:
                    pass

        if is_ajax:
            return jsonify({'success': True, 'message': success_msg})
        flash(success_msg, 'success')
        return redirect(url_for('auth.login'))

    except Exception:
        logging.exception('Forgot password error')
        if is_ajax:
            return jsonify({'success': False, 'message': 'حدث خطأ في معالجة الطلب'}), 500
        flash('حدث خطأ في معالجة الطلب', 'error')
        return render_template('auth/forgot_password.html')


@auth_bp.route('/reset-password/<token>/<int:user_id>', methods=['GET', 'POST'])
def reset_password(token: str, user_id: int) -> ResponseReturnValue:
    """صفحة إعادة تعيين كلمة المرور برمز مؤقت"""
    if not _verify_reset_token(user_id, token):
        flash('رمز إعادة التعيين غير صالح أو منتهي الصلاحية', 'error')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'GET':
        token = generate_csrf()
        from flask import make_response

        resp = make_response(
            render_template('auth/reset_password.html', token=token, user_id=user_id)
        )
        secure = current_app.config.get('SESSION_COOKIE_SECURE', True)
        resp.set_cookie('csrf_token', token, samesite='Lax', secure=secure)
        return resp

    # POST - Process password reset
    try:
        is_ajax = request.headers.get('Content-Type') == 'application/json' or request.is_json
        data = request.get_json() if is_ajax else request.form

        # CSRF validation
        csrf_enabled = current_app.config.get('WTF_CSRF_ENABLED', True)
        if csrf_enabled:
            csrf_token = (
                request.headers.get('X-CSRFToken')
                or request.headers.get('X-CSRF-Token')
                or data.get('csrf_token')
                or request.cookies.get('csrf_token')
            )
            try:
                validate_csrf(csrf_token)
            except Exception:
                msg = 'جلسة غير صالحة، يرجى تحديث الصفحة والمحاولة مرة أخرى'
                if is_ajax:
                    return jsonify({'success': False, 'message': msg}), 400
                flash(msg, 'error')
                return render_template(
                    'auth/reset_password.html', token=token, user_id=user_id
                ), 400

        new_password = (data.get('new_password') or '').strip()
        confirm_password = (data.get('confirm_password') or '').strip()

        if not new_password or not confirm_password:
            msg = 'كلمة المرور الجديدة وتأكيدها مطلوبان'
            if is_ajax:
                return jsonify({'success': False, 'message': msg}), 400
            flash(msg, 'error')
            return render_template('auth/reset_password.html', token=token, user_id=user_id)

        if new_password != confirm_password:
            msg = 'كلمة المرور غير متطابقة'
            if is_ajax:
                return jsonify({'success': False, 'message': msg}), 400
            flash(msg, 'error')
            return render_template('auth/reset_password.html', token=token, user_id=user_id)

        # Validate password policy
        try:
            from services.password_policy_service import PasswordPolicyService

            user = db.session.get(User, user_id)
            if user:
                ok, violations = PasswordPolicyService().validate(
                    new_password,
                    user_context={
                        'username': user.username,
                        'email': user.email,
                        'first_name': user.full_name.split()[0] if user.full_name else '',
                    },
                )
                if not ok:
                    msg = '; '.join(violations)
                    if is_ajax:
                        return jsonify({'success': False, 'message': msg}), 400
                    flash(msg, 'error')
                    return render_template('auth/reset_password.html', token=token, user_id=user_id)
        except ImportError:
            pass

        # Update password and invalidate sessions
        user = db.session.get(User, user_id)
        if user:
            user.set_password(new_password, enforce_policy=False)
            user.session_version = (user.session_version or 0) + 1
            _clear_reset_token(user_id)
            safe_commit(db.session, error_message='database commit failed', reraise=True)

            # Log audit trail
            try:
                from models.audit_trail import AuditTrail

                db.session.add(
                    AuditTrail(
                        entity_type='user',
                        entity_id=user.id,
                        action='password_reset',
                        user_id=user.id,
                        user_ip=request.remote_addr,
                        user_agent=request.headers.get('User-Agent'),
                        description='إعادة تعيين كلمة المرور عبر رابط استعادة',
                    )
                )
                safe_commit(db.session, error_message='database commit failed', reraise=True)
            except Exception:
                pass

        if is_ajax:
            return jsonify(
                {
                    'success': True,
                    'message': 'تم إعادة تعيين كلمة المرور بنجاح',
                    'redirect_url': url_for('auth.login'),
                }
            )
        flash('تم إعادة تعيين كلمة المرور بنجاح', 'success')
        return redirect(url_for('auth.login'))

    except Exception:
        logging.exception('Reset password error')
        if is_ajax:
            return jsonify({'success': False, 'message': 'حدث خطأ في إعادة تعيين كلمة المرور'}), 500
        flash('حدث خطأ في إعادة تعيين كلمة المرور', 'error')
        return render_template('auth/reset_password.html', token=token, user_id=user_id)


def get_redirect_url_by_role(role):
    """تحديد الصفحة المناسبة حسب الدور - legacy fallback"""
    from flask import current_app

    with current_app.test_request_context():
        from services.dashboard_routing import resolve_dashboard_for_user

        # Create a mock user object for the role
        class MockUser:
            def __init__(self, role):
                self.role = role
                self.is_authenticated = True
                self.id = 0

        return url_for(resolve_dashboard_for_user(MockUser(role)))


@auth_bp.route('/impersonate/<int:user_id>', methods=['POST'])
@login_required
@role_required_json('super_admin', 'owner')
def impersonate(user_id):
    """Owner impersonates another user for visual inspection"""
    target = db.session.get(User, user_id)
    if not target or not target.is_active:
        return jsonify({'success': False, 'message': 'المستخدم غير موجود'}), 404
    if target.id == current_user.id:
        return jsonify({'success': False, 'message': 'لا يمكن انتحال شخصية نفسك'}), 400
    session['impersonator_id'] = current_user.id
    session['impersonator_role'] = current_user.role

    from models.audit_trail import AuditTrail

    db.session.add(
        AuditTrail(
            entity_type='user',
            entity_id=target.id,
            tenant_id=target.tenant_id,
            action='IMPERSONATE',
            user_id=current_user.id,
            user_ip=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            description=f'انتحال هوية المستخدم {target.username}',
            notes=f'actor={current_user.username}, target_user_id={target.id}',
        )
    )
    safe_commit(db.session, error_message='impersonation audit write failed')

    login_user(target)
    from services.dashboard_routing import resolve_dashboard_for_user

    redirect_url = resolve_dashboard_for_user(target.role, target.tenant_id)
    return jsonify(
        {
            'success': True,
            'message': f'تم التبديل إلى {target.full_name}',
            'redirect_url': redirect_url,
        }
    )


@auth_bp.route('/impersonate/exit', methods=['POST'])
@login_required
def impersonate_exit():
    """Exit impersonation and return to owner session"""
    impersonator_id = session.pop('impersonator_id', None)
    session.pop('impersonator_role', None)
    if not impersonator_id:
        return jsonify({'success': False, 'message': 'لا توجد جلسة انتحال'}), 400
    owner = db.session.get(User, impersonator_id)
    if not owner:
        logout_user()
        return jsonify({'success': False, 'message': 'تم تسجيل الخروج'}), 401
    login_user(owner)

    from models.audit_trail import AuditTrail

    db.session.add(
        AuditTrail(
            entity_type='user',
            entity_id=owner.id,
            tenant_id=owner.tenant_id,
            action='IMPERSONATE',
            user_id=owner.id,
            user_ip=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            description='إنهاء جلسة انتحال هوية والعودة لحساب المالك',
            notes=f'actor={owner.username}, ended_target_session=True',
        )
    )
    safe_commit(db.session, error_message='impersonation exit audit write failed')

    return jsonify(
        {
            'success': True,
            'message': 'تم العودة إلى حساب المالك',
            'redirect_url': url_for('owner.owner_dashboard'),
        }
    )


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Register - redirects to SaaS signup for public registration"""
    mode = request.args.get('mode', '') if request.method == 'GET' else request.form.get('mode', '')
    if mode == 'owner':
        return redirect(url_for('owner.owner_dashboard'))
    # Public SaaS registration goes to the SaaS signup flow
    return redirect(url_for('saas.signup_organization'))
