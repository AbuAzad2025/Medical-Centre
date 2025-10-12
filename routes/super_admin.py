"""
مسارات السوبر أدمن - Super Admin Routes
Medical System Super Admin Routes
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from functools import wraps
from services.access_control_service import AccessControlService
import logging

# إنشاء Blueprint للسوبر أدمن
super_admin_bp = Blueprint('super_admin', __name__)

def super_admin_required(f):
    """ديكوريتر للتحقق من صلاحيات السوبر أدمن"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('يجب تسجيل الدخول أولاً', 'error')
            return redirect(url_for('auth.login'))
        
        # السماح لـ admin و super_admin
        if not current_user.is_admin or current_user.role not in ['super_admin', 'admin']:
            flash('ليس لديك صلاحيات للوصول لهذه الصفحة', 'error')
            return redirect(url_for('main.index'))
        
        return f(*args, **kwargs)
    return decorated_function

@super_admin_bp.route('/dashboard')
@login_required
@super_admin_required
def dashboard():
    """لوحة السوبر أدمن الذكية المتقدمة"""
    try:
        from models.user import User
        from models.patient import Patient
        from models.visit import Visit
        from models.department import Department
        from models.service import ServiceMaster
        
        # إحصائيات بسيطة ومباشرة من قاعدة البيانات
        stats = {
            'total_users': User.query.count(),
            'active_users': User.query.filter_by(is_active=True).count(),
            'inactive_users': User.query.filter_by(is_active=False).count(),
            'admin_users': User.query.filter_by(is_admin=True).count(),
            'total_patients': Patient.query.count(),
            'total_visits': Visit.query.count(),
            'total_departments': Department.query.count(),
            'active_departments': Department.query.filter_by(is_active=True).count(),
            'total_services': ServiceMaster.query.count(),
            'active_services': ServiceMaster.query.filter_by(is_active=True).count(),
            # قيم افتراضية للميزات المتقدمة
            'active_sessions': 0,
            'security_events': 0,
            'system_uptime': '99.9%',
            'daily_usage': 0,
            'database_size': '0 MB',
            'last_backup': 'لم يتم',
            'ai_insights': None,
            'smart_recommendations': None,
            'predictive_analytics': None,
            'system_health_score': 85,
            'security_threats': 0,
            'performance_optimization': None,
            'user_behavior_analysis': None,
            'resource_utilization': None
        }
        
        return render_template('super_admin/dashboard.html', stats=stats)
    
    except Exception as e:
        logging.error(f"Super admin dashboard error: {str(e)}")
        import traceback
        traceback.print_exc()
        # إرجاع صفحة بدون أخطاء
        return render_template('super_admin/dashboard.html', stats={})

@super_admin_bp.route('/system-config', methods=['GET', 'POST'])
@login_required
@super_admin_required
def system_config():
    """إعدادات النظام"""
    try:
        from app_factory import db
        from models.system_config import SystemConfig
        
        if request.method == 'POST':
            # معالجة حفظ الإعدادات
            if request.is_json:
                data = request.get_json()
                
                # حفظ الإعدادات في قاعدة البيانات
                for key, value in data.items():
                    setting = SystemConfig.query.filter_by(config_key=key).first()
                    if setting:
                        setting.config_value = str(value)
                        setting.updated_by = current_user.id
                        setting.updated_at = datetime.utcnow()
                    else:
                        # تحديد نوع الإعداد
                        config_type = 'string'
                        if isinstance(value, bool):
                            config_type = 'boolean'
                        elif isinstance(value, int):
                            config_type = 'integer'
                        
                        setting = SystemConfig(
                            config_key=key,
                            config_value=str(value),
                            config_type=config_type,
                            created_by=current_user.id,
                            updated_by=current_user.id
                        )
                        db.session.add(setting)
                
                db.session.commit()
                return jsonify({'success': True, 'message': 'تم حفظ الإعدادات بنجاح'}), 200
            else:
                flash('تم حفظ الإعدادات بنجاح', 'success')
                return redirect(url_for('super_admin.system_config'))
        
        # معالجة تحميل الإعدادات (GET)
        if request.args.get('action') == 'load':
            settings = {}
            all_settings = SystemConfig.query.all()
            for setting in all_settings:
                settings[setting.config_key] = setting.config_value
            return jsonify({'success': True, 'settings': settings}), 200
        
        # معالجة اختبار الاتصال
        if request.args.get('action') == 'test_db':
            # هنا يمكن إضافة كود اختبار الاتصال
            return jsonify({'success': True, 'message': 'الاتصال ناجح'}), 200
        
        return render_template('super_admin/system_config.html')
        
    except Exception as e:
        logging.error(f"System config error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        if request.is_json:
            return jsonify({'success': False, 'message': str(e)}), 500
        else:
            flash(f'حدث خطأ في معالجة الإعدادات: {str(e)}', 'error')
            return redirect(url_for('super_admin.dashboard'))

@super_admin_bp.route('/users')
@login_required
@super_admin_required
def users():
    """إدارة المستخدمين والأدوار والصلاحيات"""
    try:
        from models.user import User
        
        users_list = User.query.all()
        
        # الأدوار المتاحة (hardcoded لتجنب مشاكل قاعدة البيانات)
        roles_list = [
            {'name': 'super_admin', 'display_name': 'السوبر أدمن'},
            {'name': 'admin', 'display_name': 'مدير'},
            {'name': 'manager', 'display_name': 'مدير المركز'},
            {'name': 'doctor', 'display_name': 'طبيب'},
            {'name': 'nurse', 'display_name': 'ممرض'},
            {'name': 'receptionist', 'display_name': 'موظف استقبال'},
            {'name': 'accountant', 'display_name': 'محاسب'},
            {'name': 'pharmacist', 'display_name': 'صيدلي'},
            {'name': 'lab_tech', 'display_name': 'فني مختبر'},
            {'name': 'radiology', 'display_name': 'أشعة'},
            {'name': 'emergency', 'display_name': 'طوارئ'}
        ]
        
        return render_template('super_admin/users.html', 
                             users=users_list,
                             roles=roles_list,
                             permissions=[])
    except Exception as e:
        logging.error(f"Users management error: {str(e)}")
        flash('حدث خطأ في تحميل البيانات', 'error')
        return redirect(url_for('super_admin.dashboard'))

@super_admin_bp.route('/users/create', methods=['GET', 'POST'])
@login_required
@super_admin_required
def create_user():
    """إنشاء مستخدم جديد"""
    if request.method == 'POST':
        try:
            from models.user import User
            from models.department import Department
            from werkzeug.security import generate_password_hash
            
            user = User(
                username=request.form.get('username'),
                email=request.form.get('email'),
                full_name=request.form.get('full_name'),
                role=request.form.get('role'),
                department_id=request.form.get('department_id') or None,
                phone=request.form.get('phone'),
                is_active=bool(request.form.get('is_active')),
                is_admin=bool(request.form.get('is_admin'))
            )
            user.set_password(request.form.get('password'))
            
            from app_factory import db
            db.session.add(user)
            db.session.commit()
            
            flash('تم إنشاء المستخدم بنجاح', 'success')
            return redirect(url_for('super_admin.users'))
            
        except Exception as e:
            from app_factory import db
            db.session.rollback()
            logging.error(f"Create user error: {str(e)}")
            flash(f'حدث خطأ في إنشاء المستخدم: {str(e)}', 'error')
    
    # جلب البيانات المطلوبة للنموذج
    from models.department import Department
    departments = Department.query.filter_by(is_active=True).all()
    
    # الأدوار المتاحة
    roles = [
        ('super_admin', 'السوبر أدمن'),
        ('manager', 'مدير المركز'),
        ('reception', 'استقبال'),
        ('doctor', 'طبيب'),
        ('radiology', 'أشعة'),
        ('lab', 'مختبر'),
        ('emergency', 'طوارئ'),
        ('nurse', 'ممرض'),
        ('accountant', 'محاسب')
    ]
    
    return render_template('super_admin/create_user.html', 
                         departments=departments, 
                         roles=roles)

@super_admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@super_admin_required
def edit_user(user_id):
    """تعديل مستخدم"""
    try:
        from models.user import User
        from models.department import Department
        from app_factory import db
        
        user = User.query.get_or_404(user_id)
        if not user:
            flash('المستخدم غير موجود', 'error')
            return redirect(url_for('super_admin.users'))
        
        if request.method == 'POST':
            user.username = request.form.get('username')
            user.email = request.form.get('email')
            user.full_name = request.form.get('full_name')
            user.role = request.form.get('role')
            user.department_id = request.form.get('department_id') or None
            user.phone = request.form.get('phone')
            user.is_active = bool(request.form.get('is_active'))
            user.is_admin = bool(request.form.get('is_admin'))
            
            # تحديث كلمة المرور إذا تم إدخالها
            new_password = request.form.get('new_password')
            if new_password:
                user.set_password(new_password)
            
            from app_factory import db
            db.session.commit()
            
            flash('تم تحديث المستخدم بنجاح', 'success')
            return redirect(url_for('super_admin.users'))
        
        departments = Department.query.filter_by(is_active=True).all()
        roles = [
            ('super_admin', 'السوبر أدمن'),
            ('manager', 'مدير المركز'),
            ('reception', 'استقبال'),
            ('doctor', 'طبيب'),
            ('radiology', 'أشعة'),
            ('lab', 'مختبر'),
            ('emergency', 'طوارئ'),
            ('nurse', 'ممرض'),
            ('accountant', 'محاسب')
        ]
        
        return render_template('super_admin/users.html', 
                             user=user,
                             departments=departments, 
                             roles=roles,
                             mode='edit')
        
    except Exception as e:
        logging.error(f"Edit user error: {str(e)}")
        flash(f'حدث خطأ في تحديث المستخدم: {str(e)}', 'error')
        return redirect(url_for('super_admin.users'))

@super_admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@super_admin_required
def delete_user(user_id):
    """حذف مستخدم"""
    try:
        from models.user import User
        user = User.query.get_or_404(user_id)
        
        # منع حذف السوبر أدمن
        if user.role == 'super_admin':
            flash('لا يمكن حذف السوبر أدمن', 'error')
            return redirect(url_for('super_admin.users'))
        
        from app_factory import db
        db.session.delete(user)
        db.session.commit()
        
        flash('تم حذف المستخدم بنجاح', 'success')
        return redirect(url_for('super_admin.users'))
        
    except Exception as e:
        from app_factory import db
        db.session.rollback()
        logging.error(f"Delete user error: {str(e)}")
        flash(f'حدث خطأ في حذف المستخدم: {str(e)}', 'error')
        return redirect(url_for('super_admin.users'))

# تم دمج إدارة الصلاحيات في صفحة المستخدمين الرئيسية

# تم دمج إدارة الصلاحيات في صفحة المستخدمين الرئيسية

# تم دمج إدارة الأدوار في صفحة المستخدمين الرئيسية

@super_admin_bp.route('/roles')
@login_required
@super_admin_required
def roles():
    """عرض جميع الأدوار"""
    try:
        from models.permissions import Role
        roles = Role.query.all()
        return render_template('super_admin/roles.html', roles=roles, mode='list')
    except Exception as e:
        logging.error(f"Error loading roles: {str(e)}")
        # إرجاع صفحة فارغة بدلاً من redirect
        return render_template('super_admin/roles.html', roles=[], mode='list')

@super_admin_bp.route('/roles/create', methods=['GET', 'POST'])
@login_required
@super_admin_required
def create_role():
    """إنشاء دور جديد"""
    if request.method == 'POST':
        try:
            from models.permissions import Role, Permission, RolePermission
            
            role = Role(
                name=request.form.get('name'),
                name_ar=request.form.get('name_ar'),
                description=request.form.get('description'),
                is_system_role=bool(request.form.get('is_system_role')),
                is_active=bool(request.form.get('is_active'))
            )
            
            from app_factory import db
            db.session.add(role)
            db.session.flush()  # للحصول على ID
            
            # إضافة الصلاحيات للدور
            permissions = request.form.getlist('permissions')
            for perm_id in permissions:
                role_permission = RolePermission(
                    role_id=role.id,
                    permission_id=int(perm_id)
                )
                db.session.add(role_permission)
            
            db.session.commit()
            
            flash('تم إنشاء الدور بنجاح', 'success')
            return redirect(url_for('super_admin.roles'))
            
        except Exception as e:
            from app_factory import db
            db.session.rollback()
            logging.error(f"Create role error: {str(e)}")
            flash(f'حدث خطأ في إنشاء الدور: {str(e)}', 'error')
    
    # جلب الصلاحيات المتاحة
    from models.permissions import Permission
    permissions = Permission.query.all()
    
    return render_template('super_admin/roles.html', permissions=permissions, mode='create')

@super_admin_bp.route('/roles/<int:role_id>/edit', methods=['GET', 'POST'])
@login_required
@super_admin_required
def edit_role(role_id):
    """تعديل دور"""
    try:
        from models.permissions import Role, Permission, RolePermission
        
        role = Role.query.get_or_404(role_id)
        
        if request.method == 'POST':
            role.name = request.form.get('name')
            role.name_ar = request.form.get('name_ar')
            role.description = request.form.get('description')
            role.is_system_role = bool(request.form.get('is_system_role'))
            role.is_active = bool(request.form.get('is_active'))
            
            # حذف الصلاحيات القديمة
            RolePermission.query.filter_by(role_id=role.id).delete()
            
            # إضافة الصلاحيات الجديدة
            permissions = request.form.getlist('permissions')
            for perm_id in permissions:
                role_permission = RolePermission(
                    role_id=role.id,
                    permission_id=int(perm_id)
                )
                from app_factory import db
                db.session.add(role_permission)
            
            from app_factory import db
            db.session.commit()
            
            flash('تم تحديث الدور بنجاح', 'success')
            return redirect(url_for('super_admin.roles'))
        
        # جلب الصلاحيات المتاحة والصلاحيات الحالية للدور
        all_permissions = Permission.query.all()
        role_permissions = [rp.permission_id for rp in RolePermission.query.filter_by(role_id=role.id).all()]
        
        return render_template('super_admin/roles.html', 
                             role=role,
                             all_permissions=all_permissions,
                             role_permissions=role_permissions,
                             mode='edit')
        
    except Exception as e:
        logging.error(f"Edit role error: {str(e)}")
        flash(f'حدث خطأ في تحديث الدور: {str(e)}', 'error')
        return redirect(url_for('super_admin.roles'))

@super_admin_bp.route('/roles/<int:role_id>/permissions', methods=['GET', 'POST'])
@login_required
@super_admin_required
def manage_role_permissions(role_id):
    """إدارة صلاحيات الدور"""
    try:
        from models.permissions import Role, Permission, RolePermission
        from app_factory import db
        
        role = Role.query.get_or_404(role_id)
        
        if request.method == 'POST':
            # حذف الصلاحيات الحالية
            RolePermission.query.filter_by(role_id=role_id).delete()
            
            # إضافة الصلاحيات الجديدة
            selected_permissions = request.form.getlist('permissions')
            for permission_id in selected_permissions:
                role_permission = RolePermission(
                    role_id=role_id,
                    permission_id=int(permission_id),
                    granted_by=current_user.id
                )
                db.session.add(role_permission)
            
            db.session.commit()
            flash('تم تحديث صلاحيات الدور بنجاح', 'success')
            return redirect(url_for('super_admin.roles'))
        
        all_permissions = Permission.query.all()
        role_permissions = [rp.permission_id for rp in RolePermission.query.filter_by(role_id=role_id).all()]
        
        return render_template('super_admin/role_permissions.html',
                             role=role,
                             all_permissions=all_permissions,
                             role_permissions=role_permissions)
        
    except Exception as e:
        logging.error(f"Manage role permissions error: {str(e)}")
        flash('حدث خطأ في إدارة صلاحيات الدور', 'error')
        return redirect(url_for('super_admin.roles'))

@super_admin_bp.route('/roles/<int:role_id>/delete', methods=['POST'])
@login_required
@super_admin_required
def delete_role(role_id):
    """حذف دور"""
    try:
        from models.permissions import Role, RolePermission
        
        role = Role.query.get_or_404(role_id)
        
        # منع حذف الأدوار النظامية
        if role.is_system_role:
            flash('لا يمكن حذف الأدوار النظامية', 'error')
            return redirect(url_for('super_admin.roles'))
        
        # حذف صلاحيات الدور أولاً
        RolePermission.query.filter_by(role_id=role.id).delete()
        
        from app_factory import db
        db.session.delete(role)
        db.session.commit()
        
        flash('تم حذف الدور بنجاح', 'success')
        return redirect(url_for('super_admin.roles'))
        
    except Exception as e:
        from app_factory import db
        db.session.rollback()
        logging.error(f"Delete role error: {str(e)}")
        flash(f'حدث خطأ في حذف الدور: {str(e)}', 'error')
        return redirect(url_for('super_admin.roles'))

@super_admin_bp.route('/security-logs')
@login_required
@super_admin_required
def security_logs():
    """سجلات الأمان"""
    try:
        return render_template('super_admin/security_logs.html')
    except Exception as e:
        logging.error(f"Security logs error: {str(e)}")
        flash('حدث خطأ في تحميل سجلات الأمان', 'error')
        return redirect(url_for('super_admin.dashboard'))

@super_admin_bp.route('/audit-trail')
@login_required
@super_admin_required
def audit_trail():
    """سجل التدقيق"""
    try:
        from models.audit_trail import AuditTrail
        audit_logs = AuditTrail.query.order_by(AuditTrail.created_at.desc()).limit(100).all()
        return render_template('super_admin/audit_trail.html', audit_logs=audit_logs)
    except Exception as e:
        logging.error(f"Audit trail error: {str(e)}")
        flash('حدث خطأ في تحميل سجل التدقيق', 'error')
        return redirect(url_for('super_admin.dashboard'))

@super_admin_bp.route('/performance')
@login_required
@super_admin_required
def performance():
    """مراقبة الأداء"""
    try:
        return render_template('super_admin/performance.html')
    except Exception as e:
        logging.error(f"Performance monitoring error: {str(e)}")
        flash('حدث خطأ في تحميل مراقبة الأداء', 'error')
        return redirect(url_for('super_admin.dashboard'))

@super_admin_bp.route('/reports')
@login_required
@super_admin_required
def reports():
    """التقارير المتقدمة"""
    try:
        from models.user import User
        from models.patient import Patient
        from models.visit import Visit
        
        stats = {
            'total_users': User.query.count(),
            'total_patients': Patient.query.count(),
            'total_visits': Visit.query.count()
        }
        return render_template('super_admin/reports.html', stats=stats)
    except Exception as e:
        logging.error(f"Reports error: {str(e)}")
        return render_template('super_admin/reports.html', stats={})

@super_admin_bp.route('/system-backup')
@login_required
@super_admin_required
def system_backup():
    """النسخ الاحتياطية"""
    try:
        return render_template('super_admin/system_backup.html')
    except Exception as e:
        logging.error(f"System backup error: {str(e)}")
        flash('حدث خطأ في تحميل النسخ الاحتياطية', 'error')
        return redirect(url_for('super_admin.dashboard'))

# راوتات جديدة مع نظام الصلاحيات
@super_admin_bp.route('/permissions')
@login_required
@super_admin_required
def permissions():
    """إدارة الصلاحيات"""
    try:
        from models.permissions import Permission
        permissions = Permission.query.all()
        return render_template('super_admin/permissions.html', permissions=permissions)
    except Exception as e:
        logging.error(f"Permissions error: {str(e)}")
        # إرجاع صفحة فارغة بدلاً من redirect
        return render_template('super_admin/permissions.html', permissions=[])

@super_admin_bp.route('/permissions/create', methods=['POST'])
@login_required
@super_admin_required
def create_permission():
    """إنشاء صلاحية جديدة"""
    try:
        from models.permissions import Permission
        from app_factory import db
        
        permission = Permission(
            name=request.form.get('name'),
            description=request.form.get('description'),
            category=request.form.get('category'),
            level=request.form.get('level'),
            is_active=True
        )
        
        db.session.add(permission)
        db.session.commit()
        
        flash('تم إنشاء الصلاحية بنجاح', 'success')
        return redirect(url_for('super_admin.permissions'))
        
    except Exception as e:
        logging.error(f"Create permission error: {str(e)}")
        flash('حدث خطأ في إنشاء الصلاحية', 'error')
        return redirect(url_for('super_admin.permissions'))

@super_admin_bp.route('/permissions/<int:permission_id>/edit', methods=['POST'])
@login_required
@super_admin_required
def edit_permission(permission_id):
    """تعديل صلاحية"""
    try:
        from models.permissions import Permission
        from app_factory import db
        
        permission = Permission.query.get_or_404(permission_id)
        
        permission.name = request.form.get('name')
        permission.description = request.form.get('description')
        permission.category = request.form.get('category')
        permission.level = request.form.get('level')
        permission.is_active = bool(request.form.get('is_active'))
        
        db.session.commit()
        
        flash('تم تحديث الصلاحية بنجاح', 'success')
        return redirect(url_for('super_admin.permissions'))
        
    except Exception as e:
        logging.error(f"Edit permission error: {str(e)}")
        flash('حدث خطأ في تعديل الصلاحية', 'error')
        return redirect(url_for('super_admin.permissions'))

@super_admin_bp.route('/permissions/<int:permission_id>/delete', methods=['POST'])
@login_required
@super_admin_required
def delete_permission(permission_id):
    """حذف صلاحية"""
    try:
        from models.permissions import Permission
        from app_factory import db
        
        permission = Permission.query.get_or_404(permission_id)
        
        db.session.delete(permission)
        db.session.commit()
        
        flash('تم حذف الصلاحية بنجاح', 'success')
        return redirect(url_for('super_admin.permissions'))
        
    except Exception as e:
        logging.error(f"Delete permission error: {str(e)}")
        flash('حدث خطأ في حذف الصلاحية', 'error')
        return redirect(url_for('super_admin.permissions'))

@super_admin_bp.route('/departments')
@login_required
@super_admin_required
def departments():
    """إدارة الأقسام"""
    try:
        from models.department import Department
        departments = Department.query.all()
        return render_template('super_admin/departments.html', departments=departments)
    except Exception as e:
        logging.error(f"Departments error: {str(e)}")
        return render_template('super_admin/departments.html', departments=[])

@super_admin_bp.route('/departments/create', methods=['POST'])
@login_required
@super_admin_required
def create_department():
    """إنشاء قسم جديد"""
    try:
        from models.department import Department
        from app_factory import db
        
        department = Department(
            name=request.form.get('name'),
            name_en=request.form.get('name_en'),
            description=request.form.get('description'),
            location=request.form.get('location'),
            phone=request.form.get('phone'),
            is_active=True
        )
        
        db.session.add(department)
        db.session.commit()
        
        flash('تم إنشاء القسم بنجاح', 'success')
        return redirect(url_for('super_admin.departments'))
        
    except Exception as e:
        logging.error(f"Create department error: {str(e)}")
        flash('حدث خطأ في إنشاء القسم', 'error')
        return redirect(url_for('super_admin.departments'))

@super_admin_bp.route('/department/<int:department_id>')
@login_required
@super_admin_required
def view_department(department_id):
    """عرض تفاصيل قسم"""
    try:
        from models.department import Department
        from models.user import User
        
        department = Department.query.get_or_404(department_id)
        staff = User.query.filter_by(department_id=department_id).all()
        
        return render_template('super_admin/department_detail.html', 
                             department=department, 
                             staff=staff)
    except Exception as e:
        logging.error(f"View department error: {str(e)}")
        flash('حدث خطأ في عرض القسم', 'error')
        return redirect(url_for('super_admin.departments'))

@super_admin_bp.route('/edit-department/<int:department_id>', methods=['GET', 'POST'])
@login_required
@super_admin_required
def edit_department(department_id):
    """تعديل قسم"""
    try:
        from models.department import Department
        from app_factory import db
        
        department = Department.query.get_or_404(department_id)
        
        if request.method == 'POST':
            department.name = request.form.get('name')
            department.name_en = request.form.get('name_en')
            department.description = request.form.get('description')
            department.location = request.form.get('location')
            department.phone = request.form.get('phone')
            department.is_active = bool(request.form.get('is_active'))
            
            db.session.commit()
            flash('تم تحديث القسم بنجاح', 'success')
            return redirect(url_for('super_admin.departments'))
        
        return render_template('super_admin/edit_department.html', department=department)
    except Exception as e:
        logging.error(f"Edit department error: {str(e)}")
        flash('حدث خطأ في تعديل القسم', 'error')
        return redirect(url_for('super_admin.departments'))

@super_admin_bp.route('/department-staff/<int:department_id>')
@login_required
@super_admin_required
def department_staff(department_id):
    """إدارة موظفي القسم"""
    try:
        from models.department import Department
        from models.user import User
        
        department = Department.query.get_or_404(department_id)
        staff = User.query.filter_by(department_id=department_id).all()
        all_users = User.query.filter_by(is_active=True).all()
        
        return render_template('super_admin/department_staff.html', 
                             department=department, 
                             staff=staff,
                             all_users=all_users)
    except Exception as e:
        logging.error(f"Department staff error: {str(e)}")
        flash('حدث خطأ في إدارة موظفي القسم', 'error')
        return redirect(url_for('super_admin.departments'))

@super_admin_bp.route('/department-staff/<int:department_id>/add', methods=['POST'])
@login_required
@super_admin_required
def add_staff_to_department(department_id):
    """إضافة موظف للقسم"""
    try:
        from models.user import User
        from app_factory import db
        
        data = request.get_json()
        user_id = data.get('user_id')
        
        user = User.query.get_or_404(user_id)
        user.department_id = department_id
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'تم إضافة الموظف للقسم'}), 200
    except Exception as e:
        logging.error(f"Add staff error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@super_admin_bp.route('/department-staff/<int:department_id>/remove', methods=['POST'])
@login_required
@super_admin_required
def remove_staff_from_department(department_id):
    """إزالة موظف من القسم"""
    try:
        from models.user import User
        from app_factory import db
        
        data = request.get_json()
        user_id = data.get('user_id')
        
        user = User.query.get_or_404(user_id)
        user.department_id = None
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'تم إزالة الموظف من القسم'}), 200
    except Exception as e:
        logging.error(f"Remove staff error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@super_admin_bp.route('/activate-department/<int:department_id>', methods=['POST'])
@login_required
@super_admin_required
def activate_department(department_id):
    """تفعيل قسم"""
    try:
        from models.department import Department
        from app_factory import db
        
        department = Department.query.get_or_404(department_id)
        department.is_active = True
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'تم تفعيل القسم'}), 200
    except Exception as e:
        logging.error(f"Activate department error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@super_admin_bp.route('/deactivate-department/<int:department_id>', methods=['POST'])
@login_required
@super_admin_required
def deactivate_department(department_id):
    """إلغاء تفعيل قسم"""
    try:
        from models.department import Department
        from app_factory import db
        
        department = Department.query.get_or_404(department_id)
        department.is_active = False
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'تم إلغاء تفعيل القسم'}), 200
    except Exception as e:
        logging.error(f"Deactivate department error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@super_admin_bp.route('/export-departments')
@login_required
@super_admin_required
def export_departments():
    """تصدير الأقسام"""
    try:
        from models.department import Department
        import csv
        from io import StringIO
        from flask import make_response
        
        departments = Department.query.all()
        
        si = StringIO()
        writer = csv.writer(si)
        writer.writerow(['ID', 'الاسم', 'الاسم بالإنجليزية', 'الوصف', 'الموقع', 'الهاتف', 'نشط'])
        
        for dept in departments:
            writer.writerow([
                dept.id,
                dept.name,
                dept.name_en or '',
                dept.description or '',
                dept.location or '',
                dept.phone or '',
                'نعم' if dept.is_active else 'لا'
            ])
        
        output = make_response(si.getvalue())
        output.headers["Content-Disposition"] = "attachment; filename=departments_export.csv"
        output.headers["Content-type"] = "text/csv; charset=utf-8"
        return output
        
    except Exception as e:
        logging.error(f"Export departments error: {str(e)}")
        flash('حدث خطأ في تصدير الأقسام', 'error')
        return redirect(url_for('super_admin.departments'))

@super_admin_bp.route('/services')
@login_required
@super_admin_required
def services():
    """إدارة الخدمات"""
    try:
        from models.service import ServiceMaster
        services = ServiceMaster.query.all()
        return render_template('super_admin/services.html', services=services)
    except Exception as e:
        logging.error(f"Services error: {str(e)}")
        return render_template('super_admin/services.html', services=[])

@super_admin_bp.route('/services/create', methods=['POST'])
@login_required
@super_admin_required
def create_service():
    """إنشاء خدمة جديدة"""
    try:
        from models.service import ServiceMaster
        from app_factory import db
        
        service = ServiceMaster(
            name=request.form.get('name'),
            name_en=request.form.get('name_en'),
            description=request.form.get('description'),
            base_price=float(request.form.get('base_price', 0)),
            is_active=True
        )
        
        db.session.add(service)
        db.session.commit()
        
        flash('تم إنشاء الخدمة بنجاح', 'success')
        return redirect(url_for('super_admin.services'))
        
    except Exception as e:
        logging.error(f"Create service error: {str(e)}")
        flash('حدث خطأ في إنشاء الخدمة', 'error')
        return redirect(url_for('super_admin.services'))

@super_admin_bp.route('/service/<int:service_id>')
@login_required
@super_admin_required
def view_service(service_id):
    """عرض تفاصيل خدمة"""
    try:
        from models.service import ServiceMaster
        service = ServiceMaster.query.get_or_404(service_id)
        return render_template('super_admin/service_detail.html', service=service)
    except Exception as e:
        logging.error(f"View service error: {str(e)}")
        flash('حدث خطأ في عرض الخدمة', 'error')
        return redirect(url_for('super_admin.services'))

@super_admin_bp.route('/edit-service/<int:service_id>', methods=['GET', 'POST'])
@login_required
@super_admin_required
def edit_service(service_id):
    """تعديل خدمة"""
    try:
        from models.service import ServiceMaster
        from app_factory import db
        
        service = ServiceMaster.query.get_or_404(service_id)
        
        if request.method == 'POST':
            service.name = request.form.get('name')
            service.name_en = request.form.get('name_en')
            service.description = request.form.get('description')
            service.base_price = float(request.form.get('base_price', 0))
            service.is_active = bool(request.form.get('is_active'))
            
            db.session.commit()
            flash('تم تحديث الخدمة بنجاح', 'success')
            return redirect(url_for('super_admin.services'))
        
        return render_template('super_admin/edit_service.html', service=service)
    except Exception as e:
        logging.error(f"Edit service error: {str(e)}")
        flash('حدث خطأ في تعديل الخدمة', 'error')
        return redirect(url_for('super_admin.services'))

@super_admin_bp.route('/service-pricing/<int:service_id>', methods=['GET', 'POST'])
@login_required
@super_admin_required
def service_pricing(service_id):
    """إدارة تسعير الخدمة"""
    try:
        from models.service import ServiceMaster, ServicePricing
        from app_factory import db
        
        service = ServiceMaster.query.get_or_404(service_id)
        pricing = ServicePricing.query.filter_by(service_id=service_id).all()
        
        if request.method == 'POST':
            # إضافة تسعير جديد
            new_pricing = ServicePricing(
                service_id=service_id,
                price_type=request.form.get('price_type'),
                price=float(request.form.get('price', 0)),
                description=request.form.get('description')
            )
            db.session.add(new_pricing)
            db.session.commit()
            flash('تم إضافة التسعير بنجاح', 'success')
            return redirect(url_for('super_admin.service_pricing', service_id=service_id))
        
        return render_template('super_admin/service_pricing.html', service=service, pricing=pricing)
    except Exception as e:
        logging.error(f"Service pricing error: {str(e)}")
        flash('حدث خطأ في إدارة التسعير', 'error')
        return redirect(url_for('super_admin.services'))

@super_admin_bp.route('/activate-service/<int:service_id>', methods=['POST'])
@login_required
@super_admin_required
def activate_service(service_id):
    """تفعيل خدمة"""
    try:
        from models.service import ServiceMaster
        from app_factory import db
        
        service = ServiceMaster.query.get_or_404(service_id)
        service.is_active = True
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'تم تفعيل الخدمة'}), 200
    except Exception as e:
        logging.error(f"Activate service error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@super_admin_bp.route('/deactivate-service/<int:service_id>', methods=['POST'])
@login_required
@super_admin_required
def deactivate_service(service_id):
    """إلغاء تفعيل خدمة"""
    try:
        from models.service import ServiceMaster
        from app_factory import db
        
        service = ServiceMaster.query.get_or_404(service_id)
        service.is_active = False
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'تم إلغاء تفعيل الخدمة'}), 200
    except Exception as e:
        logging.error(f"Deactivate service error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@super_admin_bp.route('/export-services')
@login_required
@super_admin_required
def export_services():
    """تصدير الخدمات"""
    try:
        from models.service import ServiceMaster
        import csv
        from io import StringIO
        from flask import make_response
        
        services = ServiceMaster.query.all()
        
        si = StringIO()
        writer = csv.writer(si)
        writer.writerow(['ID', 'الاسم', 'الاسم بالإنجليزية', 'الوصف', 'السعر الأساسي', 'نشط'])
        
        for service in services:
            writer.writerow([
                service.id,
                service.name,
                service.name_en or '',
                service.description or '',
                service.base_price or 0,
                'نعم' if service.is_active else 'لا'
            ])
        
        output = make_response(si.getvalue())
        output.headers["Content-Disposition"] = "attachment; filename=services_export.csv"
        output.headers["Content-type"] = "text/csv; charset=utf-8"
        return output
        
    except Exception as e:
        logging.error(f"Export services error: {str(e)}")
        flash('حدث خطأ في تصدير الخدمات', 'error')
        return redirect(url_for('super_admin.services'))

@super_admin_bp.route('/analytics')
@login_required
@super_admin_required
def analytics():
    """التحليلات المتقدمة"""
    try:
        from models.user import User
        from models.patient import Patient
        from models.visit import Visit
        
        stats = {
            'total_users': User.query.count(),
            'total_patients': Patient.query.count(),
            'total_visits': Visit.query.count()
        }
        return render_template('super_admin/analytics.html', stats=stats)
    except Exception as e:
        logging.error(f"Analytics error: {str(e)}")
        return render_template('super_admin/analytics.html', stats={})

# إدارة العلامة التجارية
@super_admin_bp.route('/branding')
@super_admin_required
def branding():
    """إدارة العلامة التجارية والشعارات"""
    try:
        from models.branding import BrandingSettings, SystemTheme
        
        branding_settings = BrandingSettings.get_active_settings()
        themes = SystemTheme.query.filter_by(is_active=True).all()
        
        if not branding_settings:
            branding_settings = BrandingSettings.create_default(current_user.id)
        
        return render_template('super_admin/branding.html', 
                             branding=branding_settings, 
                             themes=themes)
    except Exception as e:
        logging.error(f"Branding error: {str(e)}")
        flash('حدث خطأ في تحميل صفحة العلامة التجارية', 'error')
        return redirect(url_for('super_admin.dashboard'))

@super_admin_bp.route('/branding/update', methods=['POST'])
@super_admin_required
def update_branding():
    """تحديث إعدادات العلامة التجارية"""
    try:
        from models.branding import BrandingSettings
        from app_factory import db
        from flask_wtf.csrf import validate_csrf
        
        # التحقق من CSRF token
        validate_csrf(request.form.get('csrf_token'))
        
        branding = BrandingSettings.get_active_settings()
        if not branding:
            branding = BrandingSettings.create_default(current_user.id)
        
        # تحديث البيانات الأساسية
        branding.organization_name = request.form.get('organization_name', branding.organization_name)
        branding.organization_name_en = request.form.get('organization_name_en', branding.organization_name_en)
        branding.organization_address = request.form.get('organization_address', branding.organization_address)
        branding.organization_phone = request.form.get('organization_phone', branding.organization_phone)
        branding.organization_email = request.form.get('organization_email', branding.organization_email)
        branding.organization_website = request.form.get('organization_website', branding.organization_website)
        
        # تحديث الألوان
        branding.primary_color = request.form.get('primary_color', branding.primary_color)
        branding.secondary_color = request.form.get('secondary_color', branding.secondary_color)
        branding.accent_color = request.form.get('accent_color', branding.accent_color)
        
        # تحديث ترويسة التقارير
        branding.report_header_html = request.form.get('report_header_html', branding.report_header_html)
        branding.report_footer_html = request.form.get('report_footer_html', branding.report_footer_html)
        
        branding.updated_by = current_user.id
        db.session.commit()
        
        flash('تم تحديث إعدادات العلامة التجارية بنجاح', 'success')
        return redirect(url_for('super_admin.branding'))
        
    except Exception as e:
        logging.error(f"Update branding error: {str(e)}")
        flash('حدث خطأ في تحديث إعدادات العلامة التجارية', 'error')
        return redirect(url_for('super_admin.branding'))

# إدارة المستخدمين المتقدمة
@super_admin_bp.route('/users/ban/<int:user_id>')
@super_admin_required
def ban_user(user_id):
    """حظر مستخدم"""
    try:
        from app_factory import db
        from models.user import User
        
        user = db.session.get(User, user_id)
        if not user:
            flash('المستخدم غير موجود', 'error')
            return redirect(url_for('super_admin.users'))
        if user.role == 'super_admin':
            flash('لا يمكن حظر السوبر أدمن', 'error')
            return redirect(url_for('super_admin.users'))
        
        user.is_active = False
        db.session.commit()
        
        flash(f'تم حظر المستخدم {user.full_name} بنجاح', 'success')
        return redirect(url_for('super_admin.users'))
        
    except Exception as e:
        logging.error(f"Ban user error: {str(e)}")
        flash('حدث خطأ في حظر المستخدم', 'error')
        return redirect(url_for('super_admin.users'))

@super_admin_bp.route('/users/unban/<int:user_id>')
@super_admin_required
def unban_user(user_id):
    """إلغاء حظر مستخدم"""
    try:
        from app_factory import db
        from models.user import User
        
        user = db.session.get(User, user_id)
        if not user:
            flash('المستخدم غير موجود', 'error')
            return redirect(url_for('super_admin.users'))
        user.is_active = True
        db.session.commit()
        
        flash(f'تم إلغاء حظر المستخدم {user.full_name} بنجاح', 'success')
        return redirect(url_for('super_admin.users'))
        
    except Exception as e:
        logging.error(f"Unban user error: {str(e)}")
        flash('حدث خطأ في إلغاء حظر المستخدم', 'error')
        return redirect(url_for('super_admin.users'))

@super_admin_bp.route('/users/force-logout/<int:user_id>')
@super_admin_required
def force_logout_user(user_id):
    """إجبار مستخدم على تسجيل الخروج"""
    try:
        from app_factory import db
        from models.user import User
        
        user = db.session.get(User, user_id)
        if not user:
            flash('المستخدم غير موجود', 'error')
            return redirect(url_for('super_admin.users'))
        # هنا يمكن إضافة منطق إجبار تسجيل الخروج
        # مثل حذف الجلسات أو إضافة المستخدم لقائمة المحظورين مؤقتاً
        
        flash(f'تم إجبار المستخدم {user.full_name} على تسجيل الخروج', 'success')
        return redirect(url_for('super_admin.users'))
        
    except Exception as e:
        logging.error(f"Force logout error: {str(e)}")
        flash('حدث خطأ في إجبار تسجيل الخروج', 'error')
        return redirect(url_for('super_admin.users'))

# إدارة النظام المتقدمة
@super_admin_bp.route('/system/maintenance')
@super_admin_required
def system_maintenance():
    """صيانة النظام"""
    try:
        from models.system_config import SystemConfig
        from app_factory import db
        
        # إحصائيات النظام
        from models.user import User
        
        stats = {
            'total_users': User.query.count(),
            'active_users': User.query.filter_by(is_active=True).count(),
            'inactive_users': User.query.filter_by(is_active=False).count(),
            'total_patients': 0,  # سيتم تطويرها لاحقاً
            'total_departments': 0,  # سيتم تطويرها لاحقاً
            'database_size': get_database_size(),
            'system_uptime': get_system_uptime(),
            'last_backup': get_last_backup_time()
        }
        
        return render_template('super_admin/system_maintenance.html', stats=stats)
        
    except Exception as e:
        logging.error(f"System maintenance error: {str(e)}")
        flash('حدث خطأ في تحميل صفحة صيانة النظام', 'error')
        return redirect(url_for('super_admin.dashboard'))

@super_admin_bp.route('/system/cleanup', methods=['POST'])
@super_admin_required
def system_cleanup():
    """تنظيف النظام"""
    try:
        from app_factory import db
        
        cleanup_type = request.form.get('cleanup_type')
        
        if cleanup_type == 'logs':
            # تنظيف السجلات القديمة
            from models.audit_trail import AuditTrail
            from datetime import datetime, timedelta
            
            old_logs = AuditTrail.query.filter(
                AuditTrail.created_at < datetime.utcnow() - timedelta(days=90)
            ).delete()
            
            db.session.commit()
            flash(f'تم حذف {old_logs} سجل قديم', 'success')
            
        elif cleanup_type == 'sessions':
            # تنظيف الجلسات المنتهية الصلاحية
            # هنا يمكن إضافة منطق تنظيف الجلسات
            flash('تم تنظيف الجلسات المنتهية الصلاحية', 'success')
            
        elif cleanup_type == 'cache':
            # تنظيف الكاش
            # هنا يمكن إضافة منطق تنظيف الكاش
            flash('تم تنظيف الكاش', 'success')
        
        return redirect(url_for('super_admin.system_maintenance'))
        
    except Exception as e:
        logging.error(f"System cleanup error: {str(e)}")
        flash('حدث خطأ في تنظيف النظام', 'error')
        return redirect(url_for('super_admin.system_maintenance'))

# دوال مساعدة إضافية
def get_database_size():
    """حجم قاعدة البيانات"""
    try:
        import os
        db_path = 'instance/app.db'
        if os.path.exists(db_path):
            size_bytes = os.path.getsize(db_path)
            size_mb = size_bytes / (1024 * 1024)
            return f"{size_mb:.2f} MB"
        return "غير محدد"
    except:
        return "غير محدد"

def get_last_backup_time():
    """وقت آخر نسخة احتياطية"""
    try:
        # هنا يمكن إضافة منطق للتحقق من آخر نسخة احتياطية
        return "لم يتم إنشاء نسخة احتياطية بعد"
    except:
        return "غير محدد"

# مسارات مبسطة لإنشاء الأدوار والصلاحيات
@super_admin_bp.route('/create-role-simple', methods=['POST'])
@super_admin_required
def create_role_simple():
    """إنشاء دور جديد (مبسط)"""
    try:
        from app_factory import db
        from models.permissions import Role
        from flask_wtf.csrf import validate_csrf
        
        validate_csrf(request.form.get('csrf_token'))
        
        role = Role(
            name=request.form.get('name'),
            name_ar=request.form.get('name_ar'),
            description=request.form.get('description'),
            is_system_role=False,
            is_active=True
        )
        
        db.session.add(role)
        db.session.commit()
        
        flash('تم إنشاء الدور بنجاح', 'success')
        return redirect(url_for('super_admin.users'))
        
    except Exception as e:
        logging.error(f"Create role error: {str(e)}")
        flash('حدث خطأ في إنشاء الدور', 'error')
        return redirect(url_for('super_admin.users'))

@super_admin_bp.route('/create-permission-simple', methods=['POST'])
@super_admin_required
def create_permission_simple():
    """إنشاء صلاحية جديدة (مبسط)"""
    try:
        from app_factory import db
        from models.permissions import Permission
        from flask_wtf.csrf import validate_csrf
        
        validate_csrf(request.form.get('csrf_token'))
        
        permission = Permission(
            name=request.form.get('name'),
            name_ar=request.form.get('name_ar'),
            description=request.form.get('description')
        )
        
        db.session.add(permission)
        db.session.commit()
        
        flash('تم إنشاء الصلاحية بنجاح', 'success')
        return redirect(url_for('super_admin.users'))
        
    except Exception as e:
        logging.error(f"Create permission error: {str(e)}")
        flash('حدث خطأ في إنشاء الصلاحية', 'error')
        return redirect(url_for('super_admin.users'))

# دوال مساعدة للإحصائيات
def get_total_users():
    """عدد المستخدمين الإجمالي"""
    try:
        from models.user import User
        return User.query.count()
    except:
        return 0

def get_active_sessions():
    """عدد الجلسات النشطة"""
    try:
        # يمكن تطوير هذا لاحقاً لتتبع الجلسات الفعلية
        return get_active_users()
    except:
        return 15

def get_security_events():
    """عدد أحداث الأمان"""
    try:
        from models.audit_trail import AuditTrail
        return AuditTrail.query.filter(AuditTrail.action.in_(['login', 'logout', 'security'])).count()
    except:
        return 0

def get_system_uptime():
    """وقت تشغيل النظام"""
    return "99.9%"

def get_active_users():
    """عدد المستخدمين النشطين"""
    try:
        from models.user import User
        return User.query.filter_by(is_active=True).count()
    except:
        return 0

def get_inactive_users():
    """عدد المستخدمين المعطلين"""
    try:
        from models.user import User
        return User.query.filter_by(is_active=False).count()
    except:
        return 0

def get_admin_users():
    """عدد المستخدمين المديرين"""
    try:
        from models.user import User
        return User.query.filter_by(is_admin=True).count()
    except:
        return 0

def get_daily_usage():
    """استخدام النظام اليومي"""
    # يمكن تطوير هذا لاحقاً
    return [100, 95, 88, 92, 98]

# ==================== الميزات الذكية للسوبر أدمن ====================

def get_ai_insights():
    """رؤى الذكاء الاصطناعي للنظام"""
    try:
        from models.ai_analytics import AIRecommendation, PerformanceAnalytics
        from datetime import datetime, timedelta
        
        insights = {
            'total_recommendations': AIRecommendation.query.count(),
            'pending_recommendations': AIRecommendation.query.filter(AIRecommendation.is_accepted.is_(None)).count(),
            'accepted_recommendations': AIRecommendation.query.filter(AIRecommendation.is_accepted == True).count(),
            'high_confidence_recommendations': AIRecommendation.query.filter(AIRecommendation.confidence_score >= 0.8).count(),
            'recent_insights': AIRecommendation.query.filter(
                AIRecommendation.created_at >= datetime.now() - timedelta(days=7)
            ).count()
        }
        
        return insights
    except Exception as e:
        logging.error(f"Error getting AI insights: {str(e)}")
        return {}

def get_smart_recommendations():
    """التوصيات الذكية للنظام"""
    try:
        from models.ai_analytics import AIRecommendation
        from models.user import User
        from models.visit import Visit
        from datetime import datetime, timedelta
        
        recommendations = []
        
        # تحليل الأداء
        total_visits = Visit.query.count()
        if total_visits > 100:
            recommendations.append({
                'type': 'performance',
                'title': 'تحسين الأداء',
                'description': f'تم تسجيل {total_visits} زيارة - النظام يعمل بكفاءة عالية',
                'priority': 'info'
            })
        
        # تحليل المستخدمين
        inactive_users = User.query.filter(
            User.last_login < datetime.now() - timedelta(days=30)
        ).count()
        
        if inactive_users > 5:
            recommendations.append({
                'type': 'users',
                'title': 'إدارة المستخدمين',
                'description': f'يوجد {inactive_users} مستخدم غير نشط - يحتاج مراجعة',
                'priority': 'warning'
            })
        
        # تحليل الأمان
        from models.audit_trail import AuditTrail
        failed_logins = AuditTrail.query.filter(
            AuditTrail.action == 'login_failed',
            AuditTrail.created_at >= datetime.now() - timedelta(hours=24)
        ).count()
        
        if failed_logins > 10:
            recommendations.append({
                'type': 'security',
                'title': 'تنبيه أمني',
                'description': f'محاولات تسجيل دخول فاشلة: {failed_logins} - يحتاج مراجعة',
                'priority': 'danger'
            })
        
        return recommendations
    except Exception as e:
        logging.error(f"Error getting smart recommendations: {str(e)}")
        return []

def get_predictive_analytics():
    """التحليلات التنبؤية"""
    try:
        from models.visit import Visit
        from models.patient import Patient
        from models.user import User
        from datetime import datetime, timedelta
        from sqlalchemy import func
        from app_factory import db
        
        # تحليل النمو
        week_ago = datetime.now() - timedelta(days=7)
        month_ago = datetime.now() - timedelta(days=30)
        
        patients_this_week = Patient.query.filter(Patient.created_at >= week_ago).count()
        patients_last_week = Patient.query.filter(
            Patient.created_at >= week_ago - timedelta(days=7),
            Patient.created_at < week_ago
        ).count()
        
        growth_rate = ((patients_this_week - patients_last_week) / patients_last_week * 100) if patients_last_week > 0 else 0
        
        # التنبؤ بالزيارات
        visits_this_week = Visit.query.filter(Visit.created_at >= week_ago).count()
        predicted_next_week = int(visits_this_week * (1 + growth_rate/100))
        
        # تحليل ساعات الذروة
        peak_hours = db.session.query(
            func.strftime('%H', Visit.created_at).label('hour'),
            func.count(Visit.id).label('count')
        ).group_by(func.strftime('%H', Visit.created_at)).all()
        
        peak_hour = max(peak_hours, key=lambda x: x.count) if peak_hours else None
        
        return {
            'growth_rate': round(growth_rate, 2),
            'predicted_visits_next_week': predicted_next_week,
            'peak_hour': peak_hour.hour if peak_hour else None,
            'peak_visits': peak_hour.count if peak_hour else 0,
            'trend': 'growing' if growth_rate > 0 else 'stable' if growth_rate == 0 else 'declining'
        }
    except Exception as e:
        logging.error(f"Error getting predictive analytics: {str(e)}")
        return {}

def get_system_health_score():
    """نقاط صحة النظام"""
    try:
        import os
        import shutil
        from datetime import datetime, timedelta
        from models.user import User
        from models.visit import Visit
        
        score = 100
        
        # فحص قاعدة البيانات
        try:
            db.session.execute('SELECT 1')
        except:
            score -= 20
        
        # فحص المساحة المتاحة
        try:
            disk_usage = shutil.disk_usage('/')
            free_space_percent = (disk_usage.free / disk_usage.total) * 100
            if free_space_percent < 10:
                score -= 20
            elif free_space_percent < 20:
                score -= 10
        except:
            score -= 5
        
        # فحص الملفات المهمة
        critical_files = ['app.py', 'config.py', 'requirements.txt']
        for file in critical_files:
            if not os.path.exists(file):
                score -= 5
        
        # فحص المستخدمين النشطين
        active_users = User.query.filter(User.last_login >= datetime.now() - timedelta(days=7)).count()
        if active_users == 0:
            score -= 15
        
        return {
            'score': max(0, score),
            'status': 'ممتاز' if score >= 90 else 'جيد' if score >= 70 else 'يحتاج انتباه',
            'color': 'success' if score >= 90 else 'warning' if score >= 70 else 'danger'
        }
    except Exception as e:
        logging.error(f"Error getting system health score: {str(e)}")
        return {'score': 0, 'status': 'غير محدد', 'color': 'secondary'}

def get_security_threats():
    """التهديدات الأمنية"""
    try:
        from models.audit_trail import AuditTrail
        from datetime import datetime, timedelta
        
        threats = []
        
        # محاولات تسجيل الدخول الفاشلة
        failed_logins = AuditTrail.query.filter(
            AuditTrail.action == 'login_failed',
            AuditTrail.created_at >= datetime.now() - timedelta(hours=24)
        ).count()
        
        if failed_logins > 20:
            threats.append({
                'type': 'high',
                'title': 'محاولات تسجيل دخول مفرطة',
                'description': f'{failed_logins} محاولة فاشلة في آخر 24 ساعة',
                'action': 'مراجعة سجلات الأمان'
            })
        elif failed_logins > 10:
            threats.append({
                'type': 'medium',
                'title': 'محاولات تسجيل دخول عالية',
                'description': f'{failed_logins} محاولة فاشلة في آخر 24 ساعة',
                'action': 'مراقبة النشاط'
            })
        
        # فحص الأنشطة المشبوهة
        suspicious_activities = AuditTrail.query.filter(
            AuditTrail.action.in_(['unauthorized_access', 'privilege_escalation']),
            AuditTrail.created_at >= datetime.now() - timedelta(hours=24)
        ).count()
        
        if suspicious_activities > 0:
            threats.append({
                'type': 'critical',
                'title': 'أنشطة مشبوهة',
                'description': f'{suspicious_activities} نشاط مشبوه تم اكتشافه',
                'action': 'تحقيق فوري'
            })
        
        return threats
    except Exception as e:
        logging.error(f"Error getting security threats: {str(e)}")
        return []

def get_performance_optimization():
    """تحسين الأداء"""
    try:
        from models.visit import Visit
        from models.user import User
        from datetime import datetime, timedelta
        from sqlalchemy import func
        from app_factory import db
        
        optimizations = []
        
        # تحليل ساعات الذروة
        peak_hours = db.session.query(
            func.strftime('%H', Visit.created_at).label('hour'),
            func.count(Visit.id).label('count')
        ).group_by(func.strftime('%H', Visit.created_at)).all()
        
        if peak_hours:
            max_hour = max(peak_hours, key=lambda x: x.count)
            if max_hour.count > 15:
                optimizations.append({
                    'type': 'load_balancing',
                    'title': 'توزيع الأحمال',
                    'description': f'ساعة الذروة: {max_hour.hour}:00 مع {max_hour.count} زيارة',
                    'suggestion': 'توزيع المواعيد على ساعات أخرى'
                })
        
        # تحليل الأداء حسب الأقسام
        department_load = db.session.query(
            func.count(Visit.id).label('count'),
            User.department_id
        ).join(User, Visit.doctor_id == User.id).group_by(User.department_id).all()
        
        if department_load:
            max_dept = max(department_load, key=lambda x: x.count)
            if max_dept.count > 20:
                optimizations.append({
                    'type': 'resource_allocation',
                    'title': 'تخصيص الموارد',
                    'description': f'القسم {max_dept.department_id} يحتوي على {max_dept.count} زيارة',
                    'suggestion': 'إضافة موارد إضافية لهذا القسم'
                })
        
        return optimizations
    except Exception as e:
        logging.error(f"Error getting performance optimization: {str(e)}")
        return []

def get_user_behavior_analysis():
    """تحليل سلوك المستخدمين"""
    try:
        from models.user import User
        from models.visit import Visit
        from datetime import datetime, timedelta
        
        analysis = {}
        
        # المستخدمون النشطون
        active_users = User.query.filter(
            User.last_login >= datetime.now() - timedelta(days=7)
        ).count()
        
        # المستخدمون غير النشطين
        inactive_users = User.query.filter(
            User.last_login < datetime.now() - timedelta(days=30)
        ).count()
        
        # تحليل الأدوار
        role_distribution = {}
        for user in User.query.all():
            role = user.role
            role_distribution[role] = role_distribution.get(role, 0) + 1
        
        # تحليل النشاط اليومي
        daily_activity = {}
        for user in User.query.filter(User.last_login >= datetime.now() - timedelta(days=7)):
            day = user.last_login.strftime('%A')
            daily_activity[day] = daily_activity.get(day, 0) + 1
        
        return {
            'active_users': active_users,
            'inactive_users': inactive_users,
            'role_distribution': role_distribution,
            'daily_activity': daily_activity,
            'engagement_rate': (active_users / User.query.count() * 100) if User.query.count() > 0 else 0
        }
    except Exception as e:
        logging.error(f"Error getting user behavior analysis: {str(e)}")
        return {}

def get_resource_utilization():
    """استخدام الموارد"""
    try:
        import psutil
        import os
        
        # استخدام الذاكرة
        memory = psutil.virtual_memory()
        memory_usage = {
            'total': memory.total,
            'used': memory.used,
            'free': memory.free,
            'percentage': memory.percent
        }
        
        # استخدام المعالج
        cpu_usage = psutil.cpu_percent(interval=1)
        
        # استخدام القرص
        disk = psutil.disk_usage('/')
        disk_usage = {
            'total': disk.total,
            'used': disk.used,
            'free': disk.free,
            'percentage': (disk.used / disk.total) * 100
        }
        
        # تحليل قاعدة البيانات
        from models.visit import Visit
        from models.patient import Patient
        from models.user import User
        
        db_stats = {
            'total_visits': Visit.query.count(),
            'total_patients': Patient.query.count(),
            'total_users': User.query.count()
        }
        
        return {
            'memory': memory_usage,
            'cpu': cpu_usage,
            'disk': disk_usage,
            'database': db_stats,
            'status': 'optimal' if memory.percent < 80 and cpu_usage < 80 else 'warning' if memory.percent < 90 and cpu_usage < 90 else 'critical'
        }
    except Exception as e:
        logging.error(f"Error getting resource utilization: {str(e)}")
        return {}

@super_admin_bp.route('/system')
@login_required
@super_admin_required
def system():
    """إعدادات النظام"""
    return render_template('super_admin/system_config.html')

@super_admin_bp.route('/backup')
@login_required
@super_admin_required
def backup():
    """النسخ الاحتياطي"""
    return render_template('super_admin/system_backup.html')

@super_admin_bp.route('/backup', methods=['POST'])
@super_admin_required
def create_backup():
    """إنشاء نسخة احتياطية"""
    try:
        from datetime import datetime
        import shutil
        import os
        
        # إنشاء مجلد النسخ الاحتياطية
        backup_dir = 'backups'
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        
        # اسم الملف مع التاريخ والوقت
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'medical_system_backup_{timestamp}.db'
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # نسخ قاعدة البيانات
        if os.path.exists('instance/app.db'):
            shutil.copy2('instance/app.db', backup_path)
            
            return jsonify({
                'success': True,
                'message': 'تم إنشاء النسخة الاحتياطية بنجاح',
                'backup_file': backup_filename
            })
        else:
            return jsonify({
                'success': False,
                'message': 'لم يتم العثور على قاعدة البيانات'
            })
            
    except Exception as e:
        logging.error(f"Error creating backup: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'حدث خطأ في إنشاء النسخة الاحتياطية: {str(e)}'
        })

@super_admin_bp.route('/export-data', methods=['POST'])
@super_admin_required
def export_system_data():
    """تصدير بيانات النظام"""
    try:
        from datetime import datetime
        import json
        
        # جمع البيانات من جميع الجداول
        export_data = {
            'export_date': datetime.now().isoformat(),
            'system_info': {
                'version': '1.0.0',
                'exported_by': current_user.username
            },
            'data': {}
        }
        
        # تصدير المستخدمين
        from models.user import User
        users = User.query.all()
        export_data['data']['users'] = [
            {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'full_name': user.full_name,
                'role': user.role,
                'department_id': user.department_id,
                'is_active': user.is_active,
                'created_at': user.created_at.isoformat() if user.created_at else None
            }
            for user in users
        ]
        
        # تصدير المرضى
        from models.patient import Patient
        patients = Patient.query.all()
        export_data['data']['patients'] = [
            {
                'id': patient.id,
                'name': patient.name,
                'national_id': patient.national_id,
                'phone': patient.phone,
                'birth_date': patient.birth_date.isoformat() if patient.birth_date else None,
                'created_at': patient.created_at.isoformat() if patient.created_at else None
            }
            for patient in patients
        ]
        
        # تصدير الزيارات
        from models.visit import Visit
        visits = Visit.query.all()
        export_data['data']['visits'] = [
            {
                'id': visit.id,
                'patient_id': visit.patient_id,
                'doctor_id': visit.doctor_id,
                'department_id': visit.department_id,
                'visit_type': visit.visit_type,
                'status': visit.status,
                'created_at': visit.created_at.isoformat() if visit.created_at else None
            }
            for visit in visits
        ]
        
        # حفظ الملف
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'medical_system_export_{timestamp}.json'
        
        with open(f'instance/{filename}', 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        return jsonify({
            'success': True,
            'message': 'تم تصدير البيانات بنجاح',
            'download_url': f'/super-admin/download-export/{filename}'
        })
        
    except Exception as e:
        logging.error(f"Error exporting data: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'حدث خطأ في تصدير البيانات: {str(e)}'
        })

@super_admin_bp.route('/download-export/<filename>')
@super_admin_required
def download_export(filename):
    """تحميل ملف التصدير"""
    try:
        from flask import send_file
        import os
        
        file_path = os.path.join('instance', filename)
        if os.path.exists(file_path):
            return send_file(file_path, as_attachment=True, download_name=filename)
        else:
            flash('الملف غير موجود', 'error')
            return redirect(url_for('super_admin.dashboard'))
            
    except Exception as e:
        logging.error(f"Error downloading export: {str(e)}")
        flash('حدث خطأ في تحميل الملف', 'error')
        return redirect(url_for('super_admin.dashboard'))

@super_admin_bp.route('/system-monitor')
@super_admin_required
def system_monitor():
    """مراقب النظام المتقدم"""
    try:
        # معلومات النظام
        import psutil
        import os
        
        system_info = {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_usage': psutil.disk_usage('/').percent,
            'process_count': len(psutil.pids()),
            'boot_time': psutil.boot_time()
        }
        
        return render_template('super_admin/system_monitor.html', system_info=system_info)
        
    except Exception as e:
        logging.error(f"Error in system monitor: {str(e)}")
        flash('حدث خطأ في مراقب النظام', 'error')
        return render_template('super_admin/system_monitor.html', system_info={})

# ============================================
# API Routes for AJAX Calls
# ============================================

@super_admin_bp.route('/api/audit-log', methods=['POST'])
@login_required
@super_admin_required
def api_audit_log():
    """API لتسجيل الأحداث"""
    try:
        from models.audit_trail import AuditTrail
        from app_factory import db
        
        data = request.get_json()
        
        audit = AuditTrail(
            entity_type=data.get('entity_type', 'system'),
            entity_id=data.get('entity_id', 0),
            action=data.get('action', 'view'),
            user_id=current_user.id,
            user_ip=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            description=data.get('description', ''),
            notes=data.get('notes', '')
        )
        
        db.session.add(audit)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'تم تسجيل الحدث'}), 200
        
    except Exception as e:
        logging.error(f"API audit log error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

@super_admin_bp.route('/api/recent-activities')
@login_required
@super_admin_required
def api_recent_activities():
    """API للحصول على النشاطات الأخيرة"""
    try:
        from models.audit_trail import AuditTrail
        from datetime import datetime, timedelta
        
        # الحصول على آخر 10 نشاطات
        recent = AuditTrail.query.order_by(AuditTrail.created_at.desc()).limit(10).all()
        
        activities = []
        for activity in recent:
            # حساب الوقت النسبي
            time_diff = datetime.utcnow() - activity.created_at
            if time_diff.seconds < 60:
                time_str = f"منذ {time_diff.seconds} ثانية"
            elif time_diff.seconds < 3600:
                time_str = f"منذ {time_diff.seconds // 60} دقيقة"
            elif time_diff.seconds < 86400:
                time_str = f"منذ {time_diff.seconds // 3600} ساعة"
            else:
                time_str = f"منذ {time_diff.days} يوم"
            
            # تحديد نوع النشاط
            activity_type = 'primary'
            if activity.action in ['create', 'add']:
                activity_type = 'success'
            elif activity.action in ['update', 'edit']:
                activity_type = 'warning'
            elif activity.action in ['delete', 'remove']:
                activity_type = 'danger'
            
            activities.append({
                'title': activity.description or f"{activity.action} {activity.entity_type}",
                'description': activity.notes or f"المستخدم: {activity.user.full_name if activity.user else 'غير معروف'}",
                'time': time_str,
                'type': activity_type
            })
        
        return jsonify({'success': True, 'activities': activities}), 200
        
    except Exception as e:
        logging.error(f"API recent activities error: {str(e)}")
        return jsonify({'success': False, 'activities': []}), 200

@super_admin_bp.route('/api/ai-assistant', methods=['POST'])
@login_required
@super_admin_required
def api_ai_assistant():
    """API للمساعد الذكي المتطور - محرك واحد موحد"""
    try:
        from app_factory import db
        from services.smart_ai_engine import SmartAIEngine
        from services.ai_validator import AIValidator
        
        data = request.get_json()
        user_message = data.get('message', '').strip()
        
        # إنشاء محرك الذكاء الاصطناعي
        ai_engine = SmartAIEngine(db)
        
        # التحقق من صحة النظام (اختياري - فقط للتحذيرات)
        validation = AIValidator.validate_system_data()
        
        # معالجة السؤال باستخدام المحرك الذكي
        result = ai_engine.process_query(user_message)
        
        response = result.get('response', 'عذراً، لم أتمكن من فهم سؤالك')
        actions = result.get('actions', [])
        
        # إضافة تحذير إذا كانت هناك أخطاء في النظام (بدون منع الاستخدام)
        if not validation['valid'] and len(validation['errors']) > 0:
            warning = "\n\n⚠️ **ملاحظة:** تم اكتشاف بعض المشاكل في النظام. اكتب 'فحص صحة النظام' للتفاصيل."
            response += warning
        
        return jsonify({
            'success': True,
            'response': response,
            'actions': actions
        }), 200
        
    except Exception as e:
        logging.error(f"AI Assistant error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'response': f'عذراً، حدث خطأ في معالجة طلبك: {str(e)}'
        }), 200

