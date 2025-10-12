"""
نماذج الصلاحيات المتقدمة - Advanced Permissions Models
Medical System Advanced Permissions Models
"""

from datetime import datetime
from sqlalchemy import Index, CheckConstraint
from app_factory import db

class ModulePermission(db.Model):
    """نموذج صلاحيات الوحدات"""
    
    __tablename__ = 'module_permissions'
    
    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    module_name = db.Column(db.String(50), nullable=False)  # reception, doctor, lab, radiology, emergency, accounting
    
    # صلاحيات الوحدة
    can_view = db.Column(db.Boolean, default=False)
    can_create = db.Column(db.Boolean, default=False)
    can_edit = db.Column(db.Boolean, default=False)
    can_delete = db.Column(db.Boolean, default=False)
    can_approve = db.Column(db.Boolean, default=False)
    can_archive = db.Column(db.Boolean, default=False)
    
    # صلاحيات خاصة
    can_force_payment = db.Column(db.Boolean, default=False)
    can_override_limits = db.Column(db.Boolean, default=False)
    can_access_reports = db.Column(db.Boolean, default=False)
    can_manage_users = db.Column(db.Boolean, default=False)
    
    # التواريخ
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint("module_name IN ('reception', 'doctor', 'lab', 'radiology', 'emergency', 'accounting', 'admin', 'manager')", name='chk_module_name'),
        Index('idx_module_permission_role', 'role_id'),
        Index('idx_module_permission_module', 'module_name'),
        Index('idx_module_permission_created', 'created_at'),
    )
    
    # العلاقات
    role = db.relationship('Role', back_populates='module_permissions', lazy='select')
    
    def __repr__(self):
        return f'<ModulePermission {self.role.name_ar} - {self.module_name}>'
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'role_id': self.role_id,
            'role_name': self.role.name_ar if self.role else None,
            'module_name': self.module_name,
            'can_view': self.can_view,
            'can_create': self.can_create,
            'can_edit': self.can_edit,
            'can_delete': self.can_delete,
            'can_approve': self.can_approve,
            'can_archive': self.can_archive,
            'can_force_payment': self.can_force_payment,
            'can_override_limits': self.can_override_limits,
            'can_access_reports': self.can_access_reports,
            'can_manage_users': self.can_manage_users,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class DepartmentPermission(db.Model):
    """نموذج صلاحيات الأقسام"""
    
    __tablename__ = 'department_permissions'
    
    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)  # None = جميع الأقسام
    
    # صلاحيات القسم
    can_access = db.Column(db.Boolean, default=False)
    can_manage_patients = db.Column(db.Boolean, default=False)
    can_manage_visits = db.Column(db.Boolean, default=False)
    can_manage_appointments = db.Column(db.Boolean, default=False)
    can_manage_staff = db.Column(db.Boolean, default=False)
    
    # صلاحيات خاصة
    can_override_department_limits = db.Column(db.Boolean, default=False)
    can_manage_department_settings = db.Column(db.Boolean, default=False)
    
    # التواريخ
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Constraints and Indexes
    __table_args__ = (
        Index('idx_department_permission_role', 'role_id'),
        Index('idx_department_permission_department', 'department_id'),
        Index('idx_department_permission_created', 'created_at'),
    )
    
    # العلاقات
    role = db.relationship('Role', back_populates='department_permissions', lazy='select')
    department = db.relationship('Department', back_populates='role_permissions', lazy='select')
    
    def __repr__(self):
        return f'<DepartmentPermission {self.role.name_ar} - {self.department.name_ar if self.department else "All"}>'
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'role_id': self.role_id,
            'role_name': self.role.name_ar if self.role else None,
            'department_id': self.department_id,
            'department_name': self.department.name_ar if self.department else 'جميع الأقسام',
            'can_access': self.can_access,
            'can_manage_patients': self.can_manage_patients,
            'can_manage_visits': self.can_manage_visits,
            'can_manage_appointments': self.can_manage_appointments,
            'can_manage_staff': self.can_manage_staff,
            'can_override_department_limits': self.can_override_department_limits,
            'can_manage_department_settings': self.can_manage_department_settings,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


# UserPermission تم نقله إلى models/permissions.py لتجنب التكرار
