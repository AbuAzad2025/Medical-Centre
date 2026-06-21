"""
نظام الصلاحيات المتقدم
Advanced Permissions System
"""

from app_factory import db
from datetime import datetime, timezone
from app.shared.enums import PermissionLevel, PermissionCategory
from app.shared.mixins import TenantMixin

class Permission(TenantMixin, db.Model):
    """جدول الصلاحيات"""
    __tablename__ = 'permissions'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text)
    category = db.Column(db.Enum(PermissionCategory), nullable=False)
    level = db.Column(db.Enum(PermissionLevel), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # العلاقات
    role_permissions = db.relationship('RolePermission', cascade='all, delete-orphan')
    user_permissions = db.relationship('UserPermission', cascade='all, delete-orphan')

class Role(TenantMixin, db.Model):
    """جدول الأدوار"""
    __tablename__ = 'roles'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    name_ar = db.Column(db.String(100), nullable=True)
    display_name = db.Column(db.String(100), nullable=True)
    description = db.Column(db.Text)
    is_system_role = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # العلاقات
    role_permissions = db.relationship('RolePermission', cascade='all, delete-orphan')
    module_permissions = db.relationship('ModulePermission', back_populates='role', cascade='all, delete-orphan')
    department_permissions = db.relationship('DepartmentPermission', back_populates='role', cascade='all, delete-orphan')
    # users = db.relationship('User', back_populates='role_obj')
    
    # الصلاحيات بصيغة JSON
    permissions = db.Column(db.Text, nullable=True)
    
    def get_permissions_dict(self):
        """الحصول على الصلاحيات كقاموس"""
        if self.permissions:
            import json
            try:
                return json.loads(self.permissions)
            except:
                return {}
        return {}

class RolePermission(TenantMixin, db.Model):
    """جدول صلاحيات الأدوار"""
    __tablename__ = 'role_permissions'
    
    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id', ondelete='CASCADE'), nullable=False, index=True)
    permission_id = db.Column(db.Integer, db.ForeignKey('permissions.id', ondelete='CASCADE'), nullable=False, index=True)
    granted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    granted_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), index=True)
    
    # العلاقات
    role = db.relationship('Role', back_populates='role_permissions')
    permission = db.relationship('Permission', back_populates='role_permissions')
    granter = db.relationship('User', foreign_keys=[granted_by], back_populates='granted_role_permissions')
    
    # فهرس فريد مع extend_existing
    __table_args__ = (
        db.UniqueConstraint('role_id', 'permission_id', name='unique_role_permission'),
        {'extend_existing': True}
    )

class UserPermission(TenantMixin, db.Model):
    """جدول صلاحيات المستخدمين المباشرة"""
    __tablename__ = 'user_permissions'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    permission_id = db.Column(db.Integer, db.ForeignKey('permissions.id', ondelete='CASCADE'), nullable=False, index=True)
    granted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    granted_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), index=True)
    expires_at = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    
    # العلاقات
    user = db.relationship('User', foreign_keys=[user_id], back_populates='user_permissions')
    permission = db.relationship('Permission', back_populates='user_permissions')
    granter = db.relationship('User', foreign_keys=[granted_by], back_populates='granted_permissions')
    
    # فهرس فريد
    __table_args__ = (db.UniqueConstraint('user_id', 'permission_id', name='unique_user_permission'),)

class AuditLog(TenantMixin, db.Model):
    """جدول سجل التدقيق"""
    __tablename__ = 'audit_logs'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), index=True)
    action = db.Column(db.String(100), nullable=False)
    resource_type = db.Column(db.String(50), nullable=False)
    resource_id = db.Column(db.String(50))
    old_values = db.Column(db.Text)
    new_values = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # العلاقات
    user = db.relationship('User', foreign_keys=[user_id], back_populates='audit_logs')

# تم نقل SecurityEvent إلى audit_trail.py

# تم نقل SystemSettings إلى models/system_config.py كجزء من SystemConfig

# إضافة العلاقات إلى نموذج المستخدم
def add_user_relationships():
    """إضافة العلاقات إلى نموذج المستخدم"""
    from models.user import User
    
    # إضافة العلاقات إذا لم تكن موجودة
    if not hasattr(User, 'role_obj'):
        User.role_obj = db.relationship('Role', back_populates='users')
    
    if not hasattr(User, 'user_permissions'):
        User.user_permissions = db.relationship('UserPermission', back_populates='user')
    
    if not hasattr(User, 'audit_logs'):
        User.audit_logs = db.relationship('AuditLog', back_populates='user')
    
    if not hasattr(User, 'security_events'):
        User.security_events = db.relationship('SecurityEvent', back_populates='user')

# دالة إنشاء الصلاحيات الافتراضية
def create_default_permissions():
    """إنشاء الصلاحيات الافتراضية"""
    permissions = [
        # إدارة المستخدمين
        ('user_create', 'إنشاء مستخدمين جدد', PermissionCategory.USER_MANAGEMENT, PermissionLevel.WRITE),
        ('user_read', 'عرض بيانات المستخدمين', PermissionCategory.USER_MANAGEMENT, PermissionLevel.READ),
        ('user_update', 'تعديل بيانات المستخدمين', PermissionCategory.USER_MANAGEMENT, PermissionLevel.WRITE),
        ('user_delete', 'حذف المستخدمين', PermissionCategory.USER_MANAGEMENT, PermissionLevel.DELETE),
        ('user_manage_roles', 'إدارة أدوار المستخدمين', PermissionCategory.USER_MANAGEMENT, PermissionLevel.ADMIN),
        ('user_reset_password', 'إعادة تعيين كلمات المرور', PermissionCategory.USER_MANAGEMENT, PermissionLevel.ADMIN),
        ('user_manage_permissions', 'إدارة صلاحيات المستخدمين', PermissionCategory.USER_MANAGEMENT, PermissionLevel.SUPER_ADMIN),
        
        # إدارة المرضى
        ('patient_create', 'إضافة مرضى جدد', PermissionCategory.PATIENT_MANAGEMENT, PermissionLevel.WRITE),
        ('patient_read', 'عرض بيانات المرضى', PermissionCategory.PATIENT_MANAGEMENT, PermissionLevel.READ),
        ('patient_update', 'تعديل بيانات المرضى', PermissionCategory.PATIENT_MANAGEMENT, PermissionLevel.WRITE),
        ('patient_delete', 'حذف المرضى', PermissionCategory.PATIENT_MANAGEMENT, PermissionLevel.DELETE),
        ('patient_medical_history', 'عرض التاريخ الطبي', PermissionCategory.PATIENT_MANAGEMENT, PermissionLevel.READ),
        ('patient_export_data', 'تصدير بيانات المرضى', PermissionCategory.PATIENT_MANAGEMENT, PermissionLevel.ADMIN),
        
        # السجلات الطبية
        ('medical_records_create', 'إنشاء سجلات طبية', PermissionCategory.MEDICAL_RECORDS, PermissionLevel.WRITE),
        ('medical_records_read', 'عرض السجلات الطبية', PermissionCategory.MEDICAL_RECORDS, PermissionLevel.READ),
        ('medical_records_update', 'تعديل السجلات الطبية', PermissionCategory.MEDICAL_RECORDS, PermissionLevel.WRITE),
        ('medical_records_delete', 'حذف السجلات الطبية', PermissionCategory.MEDICAL_RECORDS, PermissionLevel.DELETE),
        ('medical_records_export', 'تصدير السجلات الطبية', PermissionCategory.MEDICAL_RECORDS, PermissionLevel.ADMIN),
        
        # النظام المالي
        ('financial_view', 'عرض البيانات المالية', PermissionCategory.FINANCIAL, PermissionLevel.READ),
        ('financial_manage', 'إدارة النظام المالي', PermissionCategory.FINANCIAL, PermissionLevel.WRITE),
        ('financial_reports', 'عرض التقارير المالية', PermissionCategory.FINANCIAL, PermissionLevel.READ),
        ('financial_export', 'تصدير البيانات المالية', PermissionCategory.FINANCIAL, PermissionLevel.ADMIN),
        ('pricing_manage', 'إدارة الأسعار', PermissionCategory.FINANCIAL, PermissionLevel.ADMIN),
        
        # إدارة النظام
        ('system_settings', 'إدارة إعدادات النظام', PermissionCategory.SYSTEM_ADMIN, PermissionLevel.ADMIN),
        ('system_logs', 'عرض سجلات النظام', PermissionCategory.SYSTEM_ADMIN, PermissionLevel.ADMIN),
        ('system_monitoring', 'مراقبة النظام', PermissionCategory.SYSTEM_ADMIN, PermissionLevel.ADMIN),
        ('system_maintenance', 'صيانة النظام', PermissionCategory.SYSTEM_ADMIN, PermissionLevel.SUPER_ADMIN),
        
        # النسخ الاحتياطي والاستعادة
        ('backup_create', 'إنشاء نسخ احتياطية', PermissionCategory.BACKUP_RESTORE, PermissionLevel.ADMIN),
        ('backup_restore', 'استعادة النسخ الاحتياطية', PermissionCategory.BACKUP_RESTORE, PermissionLevel.SUPER_ADMIN),
        ('backup_schedule', 'جدولة النسخ الاحتياطية', PermissionCategory.BACKUP_RESTORE, PermissionLevel.SUPER_ADMIN),
        ('backup_manage', 'إدارة النسخ الاحتياطية', PermissionCategory.BACKUP_RESTORE, PermissionLevel.SUPER_ADMIN),
        
        # التقارير
        ('reports_view', 'عرض التقارير', PermissionCategory.REPORTS, PermissionLevel.READ),
        ('reports_create', 'إنشاء تقارير', PermissionCategory.REPORTS, PermissionLevel.WRITE),
        ('reports_export', 'تصدير التقارير', PermissionCategory.REPORTS, PermissionLevel.ADMIN),
        ('reports_advanced', 'التقارير المتقدمة', PermissionCategory.REPORTS, PermissionLevel.ADMIN),
        
        # الأمان
        ('security_view', 'عرض الأحداث الأمنية', PermissionCategory.SECURITY, PermissionLevel.READ),
        ('security_manage', 'إدارة الأمان', PermissionCategory.SECURITY, PermissionLevel.ADMIN),
        ('security_audit', 'تدقيق الأمان', PermissionCategory.SECURITY, PermissionLevel.SUPER_ADMIN),
        
        # التدقيق
        ('audit_view', 'عرض سجلات التدقيق', PermissionCategory.AUDIT, PermissionLevel.ADMIN),
        ('audit_export', 'تصدير سجلات التدقيق', PermissionCategory.AUDIT, PermissionLevel.SUPER_ADMIN),
        ('audit_manage', 'إدارة التدقيق', PermissionCategory.AUDIT, PermissionLevel.SUPER_ADMIN),
        # إعدادات الطوابير
        ('queue_settings_manage', 'إدارة إعدادات الطابور', PermissionCategory.SETTINGS, PermissionLevel.ADMIN),
    ]
    
    for name, description, category, level in permissions:
        permission = Permission.query.filter_by(name=name).first()
        if not permission:
            permission = Permission(
                name=name,
                description=description,
                category=category,
                level=level
            )
            db.session.add(permission)
    
    db.session.commit()

# دالة إنشاء الأدوار الافتراضية
def create_default_roles():
    """إنشاء الأدوار الافتراضية"""
    roles = [
        ('super_admin', 'السوبر أدمن', 'مدير النظام الأعلى', True),
        ('admin', 'مدير النظام', 'مدير النظام', True),
        ('manager', 'مدير المركز', 'مدير المركز', True),
        ('reception', 'استقبال', 'موظف الاستقبال', True),
        ('doctor', 'طبيب', 'طبيب', True),
        ('radiology', 'أشعة', 'فني أشعة', True),
        ('lab', 'مختبر', 'فني مختبر', True),
        ('emergency', 'طوارئ', 'موظف طوارئ', True),
        ('nurse', 'ممرض', 'ممرض', True),
        ('accountant', 'محاسب', 'محاسب', True),
        ('pharmacist', 'صيدلي', 'صيدلي', True),
        ('technician', 'فني', 'فني طبي', True),
        ('receptionist', 'استقبال', 'موظف استقبال', True),
        ('lab_tech', 'فني مختبر', 'فني مختبر', True),
        ('owner', 'مالك', 'مالك المركز', True),
    ]
    
    for name, name_ar, description, is_system in roles:
        role = Role.query.filter_by(name=name).first()
        if not role:
            role = Role(
                name=name,
                name_ar=name_ar,
                display_name=name_ar,
                description=description,
                is_system_role=is_system
            )
            db.session.add(role)
    
    db.session.commit()

# دالة تعيين صلاحيات السوبر أدمن
def assign_super_admin_permissions():
    """تعيين جميع الصلاحيات للسوبر أدمن"""
    super_admin_role = Role.query.filter_by(name='super_admin').first()
    if not super_admin_role:
        return
    
    # الحصول على جميع الصلاحيات
    all_permissions = Permission.query.all()
    
    for permission in all_permissions:
        # التحقق من وجود الصلاحية للدور
        role_permission = RolePermission.query.filter_by(
            role_id=super_admin_role.id,
            permission_id=permission.id
        ).first()
        
        if not role_permission:
            role_permission = RolePermission(
                role_id=super_admin_role.id,
                permission_id=permission.id
            )
            db.session.add(role_permission)
    
    db.session.commit()
