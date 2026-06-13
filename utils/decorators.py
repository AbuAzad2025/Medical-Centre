"""
Decorators للصلاحيات ومراقبة الوصول
"""
from functools import wraps
from flask import flash, redirect, url_for, abort, request, jsonify
from flask_login import current_user
import logging

logger = logging.getLogger(__name__)


def _get_language():
    h = (request.headers.get('Accept-Language') or '').lower()
    return 'en' if 'en' in h else 'ar'


def _format_message(key):
    lang = _get_language()
    role = None
    try:
        role = current_user.role if current_user.is_authenticated else None
    except Exception:
        role = None
    ar = {
        'not_authenticated': 'يرجى تسجيل الدخول للمتابعة',
        'no_permission': 'لا تملك صلاحية الوصول إلى هذه الصفحة',
        'no_permission_doctor': 'الوصول إلى الوحدة السريرية يتطلب صلاحيات طبية مناسبة. يرجى التنسيق مع الإدارة',
        'no_permission_nurse': 'الوصول يتطلب صلاحيات تمريضية مناسبة. يرجى التواصل مع الإدارة',
        'no_permission_lab': 'الوصول إلى وحدة الفحوصات يتطلب صلاحيات مخبرية سارية',
        'no_permission_radiology': 'الوصول إلى وحدة التصوير يتطلب صلاحيات تصويرية سارية',
        'reception_only': 'هذه الصفحة مخصصة للاستقبال فقط',
        'accountant_only': 'هذه الصفحة مخصصة للمحاسب فقط',
        'manager_admin_only': 'هذه الصفحة مخصصة للمدير أو المدير الأعلى فقط',
        'payments_not_allowed': 'لست مفوّضاً لمعالجة الدفعات. يرجى تحويل العملية للمحاسب',
        'force_payment_manager_only': 'الموافقة على الدفع القسري محصورة بالمدير فقط',
        'visit_create_reception_only': 'إنشاء الزيارات محصور بالاستقبال. يرجى التواصل مع الإدارة عند الحاجة',
        'patient_modify_not_allowed': 'لا تملك صلاحية تعديل بيانات المرضى. يرجى إرسال الطلب للإدارة',
        'financial_reports_not_allowed': 'لا تملك صلاحية الوصول للتقارير المالية',
        'visit_archive_not_allowed': 'لا تملك صلاحية أرشفة الزيارات'
    }
    en = {
        'not_authenticated': 'Please sign in to continue',
        'no_permission': 'You do not have permission to access this page',
        'no_permission_doctor': 'Access to this clinical unit requires appropriate clinical privileges. Please coordinate with administration',
        'no_permission_nurse': 'Access requires appropriate nursing privileges. Please contact administration',
        'no_permission_lab': 'Access to diagnostics requires valid laboratory privileges',
        'no_permission_radiology': 'Access to imaging requires valid radiology privileges',
        'reception_only': 'This page is for reception only',
        'accountant_only': 'This page is for accountants only',
        'manager_admin_only': 'This page is for managers or super admins only',
        'payments_not_allowed': 'You are not authorized to process payments. Please refer to accounting',
        'force_payment_manager_only': 'Forced payment approval is restricted to managers',
        'visit_create_reception_only': 'Visit creation is restricted to reception. Please coordinate with administration if needed',
        'patient_modify_not_allowed': 'You are not authorized to modify patient data. Please submit a request to administration',
        'financial_reports_not_allowed': 'You are not authorized to access financial reports',
        'visit_archive_not_allowed': 'You are not authorized to archive visits'
    }
    base = en if lang == 'en' else ar
    if key == 'no_permission':
        if role == 'doctor':
            return base.get('no_permission_doctor', base['no_permission'])
        if role == 'nurse':
            return base.get('no_permission_nurse', base['no_permission'])
        if role == 'lab':
            return base.get('no_permission_lab', base['no_permission'])
        if role == 'radiology':
            return base.get('no_permission_radiology', base['no_permission'])
    return base.get(key, base['no_permission'])


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
                flash(_format_message('not_authenticated'), 'error')
                return redirect(url_for('auth.login'))
            
            if current_user.role not in roles:
                logger.warning(f"Access denied: User {current_user.id} ({current_user.role}) tried to access {request.endpoint}")
                flash(_format_message('no_permission'), 'error')
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def reception_only(f):
    """ديكوريتر للاستقبال فقط"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash(_format_message('not_authenticated'), 'error')
            return redirect(url_for('auth.login'))
        
        if current_user.role not in ['reception', 'manager', 'super_admin']:
            logger.warning(f"Reception access denied for user {current_user.id} ({current_user.role})")
            flash(_format_message('reception_only'), 'error')
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function


def accountant_only(f):
    """ديكوريتر للمحاسب فقط"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash(_format_message('not_authenticated'), 'error')
            return redirect(url_for('auth.login'))
        
        if current_user.role not in ['accountant', 'manager', 'super_admin']:
            logger.warning(f"Accountant access denied for user {current_user.id} ({current_user.role})")
            flash(_format_message('accountant_only'), 'error')
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function


def manager_or_admin_only(f):
    """ديكوريتر للمدير أو super_admin فقط"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash(_format_message('not_authenticated'), 'error')
            return redirect(url_for('auth.login'))
        
        if current_user.role not in ['manager', 'super_admin']:
            logger.warning(f"Manager/Admin access denied for user {current_user.id} ({current_user.role})")
            flash(_format_message('manager_admin_only'), 'error')
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function


def super_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash(_format_message('not_authenticated'), 'error')
            return redirect(url_for('auth.login'))
        if not current_user.is_admin or current_user.role not in ['super_admin', 'admin']:
            flash(_format_message('no_permission'), 'error')
            return redirect(url_for('main.index'))
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
            flash(_format_message('not_authenticated'), 'error')
            return redirect(url_for('auth.login'))
        
        allowed_roles = ['reception', 'accountant', 'manager', 'super_admin']
        if current_user.role not in allowed_roles:
            logger.warning(f"Payment handling denied for user {current_user.id} ({current_user.role})")
            flash(_format_message('payments_not_allowed'), 'error')
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
            flash(_format_message('not_authenticated'), 'error')
            return redirect(url_for('auth.login'))
        
        if current_user.role not in ['manager', 'super_admin']:
            logger.warning(f"Force payment approval denied for user {current_user.id} ({current_user.role})")
            flash(_format_message('force_payment_manager_only'), 'error')
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function


def can_create_visits(f):
    """
    ديكوريتر للتحقق من صلاحية إنشاء زيارات
    حصرياً للاستقبال
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash(_format_message('not_authenticated'), 'error')
            return redirect(url_for('auth.login'))
        
        allowed_roles = ['reception']
        if current_user.role not in allowed_roles:
            logger.warning(f"Visit creation denied for user {current_user.id} ({current_user.role})")
            flash(_format_message('visit_create_reception_only'), 'error')
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
            flash(_format_message('not_authenticated'), 'error')
            return redirect(url_for('auth.login'))
        
        allowed_roles = ['reception', 'manager', 'super_admin']
        if current_user.role not in allowed_roles:
            logger.warning(f"Patient data modification denied for user {current_user.id} ({current_user.role})")
            flash(_format_message('patient_modify_not_allowed'), 'error')
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function


def can_delete_patient(f):
    """
    ديكوريتر للتحقق من صلاحية حذف المريض - صلاحية إدارية صارمة
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash(_format_message('not_authenticated'), 'error')
            return redirect(url_for('auth.login'))
        
        allowed_roles = ['manager', 'super_admin']
        if current_user.role not in allowed_roles:
            logger.warning(f"Patient deletion denied for user {current_user.id} ({current_user.role})")
            flash(_format_message('patient_delete_not_allowed'), 'error')
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
            flash(_format_message('not_authenticated'), 'error')
            return redirect(url_for('auth.login'))
        
        allowed_roles = ['accountant', 'manager', 'super_admin']
        if current_user.role not in allowed_roles:
            logger.warning(f"Financial reports access denied for user {current_user.id} ({current_user.role})")
            flash(_format_message('financial_reports_not_allowed'), 'error')
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
            flash(_format_message('not_authenticated'), 'error')
            return redirect(url_for('auth.login'))
        
        allowed_roles = ['reception', 'manager']
        if current_user.role not in allowed_roles:
            logger.warning(f"Visit archiving denied for user {current_user.id} ({current_user.role})")
            flash(_format_message('visit_archive_not_allowed'), 'error')
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
            from app_factory import db
            visit = db.session.get(Visit, visit_id)
            
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
            from app_factory import db
            visit = db.session.get(Visit, visit_id)
            
            if visit and visit.created_by == current_user.id:
                logger.warning(f"Self-approval attempt: User {current_user.id} tried to approve own visit {visit_id}")
                flash('لا يمكنك الموافقة على زيارة أنشأتها بنفسك (فصل المهام)', 'error')
                abort(403)
        
        return f(*args, **kwargs)
    return decorated_function

def role_required_json(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                if (request.headers.get('Accept') or '').lower().find('application/json') != -1 or (request.headers.get('X-Requested-With') or '').lower() == 'xmlhttprequest':
                    return jsonify({'success': False, 'message': _format_message('not_authenticated')}), 401
                flash(_format_message('not_authenticated'), 'error')
                return redirect(url_for('auth.login'))
            if current_user.role not in roles:
                if (request.headers.get('Accept') or '').lower().find('application/json') != -1 or (request.headers.get('X-Requested-With') or '').lower() == 'xmlhttprequest':
                    return jsonify({'success': False, 'message': _format_message('no_permission')}), 403
                flash(_format_message('no_permission'), 'error')
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def super_admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash(_format_message('not_authenticated'), 'error')
            return redirect(url_for('auth.login'))
        try:
            is_sa = getattr(current_user, 'is_super_admin', None)
            is_sa_val = is_sa() if callable(is_sa) else False
        except Exception:
            is_sa_val = False
        if not is_sa_val:
            flash(_format_message('no_permission'), 'error')
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

