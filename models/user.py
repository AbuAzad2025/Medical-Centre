"""
نموذج المستخدم - User Model (نسخة نهائية)
"""
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Index, CheckConstraint
from app_factory import db


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='user')

    department_id = db.Column(
        db.Integer,
        db.ForeignKey('departments.id', use_alter=True, ondelete='SET NULL'),
        nullable=True,
        index=True
    )

    phone = db.Column(db.String(20), nullable=True)
    is_active = db.Column(db.Boolean, default=True, index=True)
    is_admin = db.Column(db.Boolean, default=False, index=True)

    last_login = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (
        CheckConstraint("length(username) >= 3", name='chk_user_username_len'),
        Index('idx_user_role', 'role'),
    )

    department = db.relationship(
        'Department',
        back_populates='users',
        foreign_keys=[department_id],
        lazy='selectin'
    )

    head_of_department = db.relationship(
        'Department',
        foreign_keys='Department.head_doctor_id',
        back_populates='head_doctor',
        lazy='select'
    )

    doctor_visits = db.relationship(
        'Visit',
        foreign_keys='Visit.doctor_id',
        back_populates='doctor',
        lazy='selectin'
    )

    doctor_appointments = db.relationship(
        'Appointment',
        foreign_keys='Appointment.doctor_id',
        back_populates='doctor',
        lazy='selectin'
    )

    # علاقات التدقيق
    audit_trails = db.relationship(
        'AuditTrail',
        foreign_keys='AuditTrail.user_id',
        back_populates='user',
        lazy='selectin'
    )

    # علاقات سجلات النظام
    system_logs = db.relationship(
        'SystemLog',
        foreign_keys='SystemLog.user_id',
        back_populates='user',
        lazy='selectin'
    )

    # علاقات أحداث الأمان
    security_events = db.relationship(
        'SecurityEvent',
        foreign_keys='SecurityEvent.user_id',
        back_populates='user',
        lazy='selectin'
    )

    # علاقات أحداث الأمان المحلولة
    resolved_security_events = db.relationship(
        'SecurityEvent',
        foreign_keys='SecurityEvent.resolved_by',
        back_populates='resolver',
        lazy='selectin'
    )

    # علاقات إعدادات النظام
    created_system_configs = db.relationship(
        'SystemConfig',
        foreign_keys='SystemConfig.created_by',
        back_populates='creator',
        lazy='selectin'
    )

    updated_system_configs = db.relationship(
        'SystemConfig',
        foreign_keys='SystemConfig.updated_by',
        back_populates='updater',
        lazy='selectin'
    )

    # علاقات نظام الصلاحيات
    user_permissions = db.relationship(
        'UserPermission',
        foreign_keys='UserPermission.user_id',
        back_populates='user',
        lazy='selectin'
    )

    granted_permissions = db.relationship(
            'UserPermission',
            foreign_keys='UserPermission.granted_by',
            back_populates='granter',
            lazy='selectin'
        )

    granted_role_permissions = db.relationship(
            'RolePermission',
            foreign_keys='RolePermission.granted_by',
            back_populates='granter',
            lazy='selectin'
        )

    audit_logs = db.relationship(
            'AuditLog',
            foreign_keys='AuditLog.user_id',
            back_populates='user',
            lazy='selectin'
        )
    
    # علاقة التسعير للأطباء
    pricing = db.relationship(
        'DoctorPricing',
        foreign_keys='DoctorPricing.doctor_id',
        back_populates='doctor',
        lazy='select'
    )
    
    # علاقة الزيارات كطبيب
    doctor_visits = db.relationship(
        'Visit',
        foreign_keys='Visit.doctor_id',
        back_populates='doctor',
        lazy='select'
    )

    # علاقات الإشعارات
    notifications = db.relationship(
            'Notification',
            foreign_keys='Notification.recipient_id',
            back_populates='recipient',
            lazy='selectin'
        )

    sent_notifications = db.relationship(
            'Notification',
            foreign_keys='Notification.sender_id',
            back_populates='sender',
            lazy='selectin'
        )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:
        return f"<User {self.username}>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "role": self.role,
            "department_id": self.department_id,
            "phone": self.phone,
            "is_active": self.is_active,
            "is_admin": self.is_admin,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }