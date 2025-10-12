"""
Decorators للصلاحيات ومراقبة الوصول
"""
from functools import wraps
from flask import flash, redirect, url_for, abort, request
from flask_login import current_user
import logging

logger = logging.getLogger(__name__)


def role_required(*roles):
    """
    ديكوريتر للتحقق من دور المستخدم
    
    Usage:
        @role_required('reception', 'manager')
        def some_function():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('يجب تسجيل الدخول أولاً', 'error')
                return redirect(url_for('auth.login'))
            
            if current_user.role not in roles:
                logger.warning(f"Access denied: User {current_user.id} ({current_user.role}) tried to access {request.endpoint}")
                flash('ليس لديك صلاحيات للوصول إلى هذه الصفحة', 'error')
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def reception_only(f):
    """ديكوريتر للاستقبال فقط"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('يجب تسجيل الدخول أولاً', 'error')
            return redirect(url_for('auth.login'))
        
        if current_user.role not in ['reception', 'manager', 'super_admin']:
            logger.warning(f"Reception access denied for user {current_user.id} ({current_user.role})")
            flash('هذه الصفحة مخصصة للاستقبال فقط', 'error')
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function


def accountant_only(f):
    """ديكوريتر للمحاسب فقط"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('يجب تسجيل الدخول أولاً', 'error')
            return redirect(url_for('auth.login'))
        
        if current_user.role not in ['accountant', 'manager', 'super_admin']:
            logger.warning(f"Accountant access denied for user {current_user.id} ({current_user.role})")
            flash('هذه الصفحة مخصصة للمحاسب فقط', 'error')
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function


def manager_or_admin_only(f):
    """ديكوريتر للمدير أو super_admin فقط"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('يجب تسجيل الدخول أولاً', 'error')
            return redirect(url_for('auth.login'))
        
        if current_user.role not in ['manager', 'super_admin']:
            logger.warning(f"Manager/Admin access denied for user {current_user.id} ({current_user.role})")
            flash('هذه الصفحة مخصصة للمدير أو المدير الأعلى فقط', 'error')
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function


def can_handle_payments(f):
    """
    ديكوريتر للتحقق من صلاحية استلام الدفعات
    الأدوار المسموحة: reception, accountant, manager, super_admin
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('يجب تسجيل الدخول أولاً', 'error')
            return redirect(url_for('auth.login'))
        
        allowed_roles = ['reception', 'accountant', 'manager', 'super_admin']
        if current_user.role not in allowed_roles:
            logger.warning(f"Payment handling denied for user {current_user.id} ({current_user.role})")
            flash('ليس لديك صلاحية استلام الدفعات', 'error')
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function


def can_approve_force_payment(f):
    """
    ديكوريتر للتحقق من صلاحية الموافقة على الدفع القسري
    فقط المدير أو super_admin
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('يجب تسجيل الدخول أولاً', 'error')
            return redirect(url_for('auth.login'))
        
        if current_user.role not in ['manager', 'super_admin']:
            logger.warning(f"Force payment approval denied for user {current_user.id} ({current_user.role})")
            flash('فقط المدير يمكنه الموافقة على الدفع القسري', 'error')
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function


def can_create_visits(f):
    """
    ديكوريتر للتحقق من صلاحية إنشاء زيارات
    فقط الاستقبال, المدير, super_admin
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('يجب تسجيل الدخول أولاً', 'error')
            return redirect(url_for('auth.login'))
        
        allowed_roles = ['reception', 'manager', 'super_admin', 'emergency']
        if current_user.role not in allowed_roles:
            logger.warning(f"Visit creation denied for user {current_user.id} ({current_user.role})")
            flash('فقط الاستقبال يمكنه إنشاء الزيارات', 'error')
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function


def can_modify_patient_data(f):
    """
    ديكوريتر للتحقق من صلاحية تعديل بيانات المرضى
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('يجب تسجيل الدخول أولاً', 'error')
            return redirect(url_for('auth.login'))
        
        allowed_roles = ['reception', 'manager', 'super_admin']
        if current_user.role not in allowed_roles:
            logger.warning(f"Patient data modification denied for user {current_user.id} ({current_user.role})")
            flash('ليس لديك صلاحية تعديل بيانات المرضى', 'error')
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function


def can_access_financial_reports(f):
    """
    ديكوريتر للتحقق من صلاحية الوصول للتقارير المالية
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('يجب تسجيل الدخول أولاً', 'error')
            return redirect(url_for('auth.login'))
        
        allowed_roles = ['accountant', 'manager', 'super_admin']
        if current_user.role not in allowed_roles:
            logger.warning(f"Financial reports access denied for user {current_user.id} ({current_user.role})")
            flash('ليس لديك صلاحية الوصول للتقارير المالية', 'error')
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function


def can_archive_visits(f):
    """
    ديكوريتر للتحقق من صلاحية أرشفة الزيارات
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('يجب تسجيل الدخول أولاً', 'error')
            return redirect(url_for('auth.login'))
        
        allowed_roles = ['accountant', 'manager', 'super_admin']
        if current_user.role not in allowed_roles:
            logger.warning(f"Visit archiving denied for user {current_user.id} ({current_user.role})")
            flash('ليس لديك صلاحية أرشفة الزيارات', 'error')
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function


def log_action(action_type):
    """
    ديكوريتر لتسجيل الإجراءات المهمة في سجل التدقيق
    
    Usage:
        @log_action('create_visit')
        def create_visit():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # تنفيذ الدالة أولاً
            result = f(*args, **kwargs)
            
            # تسجيل الإجراء
            try:
                from models.audit_trail import AuditTrail
                from app_factory import db
                
                audit = AuditTrail(
                    user_id=current_user.id if current_user.is_authenticated else None,
                    action=action_type,
                    entity_type=f.__name__,
                    ip_address=request.remote_addr,
                    user_agent=request.user_agent.string,
                    description=f"User {current_user.username if current_user.is_authenticated else 'Anonymous'} performed {action_type}"
                )
                
                db.session.add(audit)
                db.session.commit()
                
                logger.info(f"Action logged: {action_type} by user {current_user.id if current_user.is_authenticated else 'Anonymous'}")
                
            except Exception as e:
                logger.error(f"Error logging action: {str(e)}")
                # لا نرفع الخطأ حتى لا نؤثر على العملية الأساسية
            
            return result
        return decorated_function
    return decorator


def require_payment_before_service(f):
    """
    ديكوريتر للتأكد من الدفع قبل تقديم الخدمة
    يُستخدم في الصفحات التي تتطلب دفع مسبق
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        visit_id = kwargs.get('visit_id') or request.args.get('visit_id')
        
        if visit_id:
            from models.visit import Visit
            visit = Visit.query.get(visit_id)
            
            if visit:
                # التحقق من الدفع
                if visit.payment_status == 'PENDING' and not visit.is_force_payment:
                    flash('يجب إتمام الدفع قبل المتابعة', 'warning')
                    return redirect(url_for('payment.process_payment', visit_id=visit_id))
                
                # إذا دفع قسري، التحقق من الموافقة
                if visit.is_force_payment and not visit.force_payment_approved_by:
                    flash('الدفع القسري يحتاج موافقة المدير', 'warning')
                    return redirect(url_for('reception.visits'))
        
        return f(*args, **kwargs)
    return decorated_function


def prevent_self_approval(f):
    """
    ديكوريتر لمنع الموافقة الذاتية (فصل المهام)
    يُستخدم في عمليات الموافقة على الدفع القسري
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        visit_id = kwargs.get('visit_id') or request.form.get('visit_id')
        
        if visit_id:
            from models.visit import Visit
            visit = Visit.query.get(visit_id)
            
            if visit and visit.created_by == current_user.id:
                logger.warning(f"Self-approval attempt: User {current_user.id} tried to approve own visit {visit_id}")
                flash('لا يمكنك الموافقة على زيارة أنشأتها بنفسك (فصل المهام)', 'error')
                abort(403)
        
        return f(*args, **kwargs)
    return decorated_function

