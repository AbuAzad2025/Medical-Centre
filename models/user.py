"""
نموذج المستخدم - User Model (نسخة نهائية)
"""
from datetime import datetime, time, date, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Index, CheckConstraint, event
from app_factory import db
from app.shared.mixins import TenantMixin


class User(TenantMixin, UserMixin, db.Model):
    __tablename__ = 'users'
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(80), nullable=False, index=True)
    email = db.Column(db.String(120), nullable=False, index=True)

    # Composite unique per tenant + existing constraints
    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'username', name='uq_user_tenant_username'),
        db.UniqueConstraint('tenant_id', 'email', name='uq_user_tenant_email'),
        CheckConstraint("length(username) >= 3", name='chk_user_username_len'),
        Index('idx_user_role', 'role'),
        Index('idx_user_department_role', 'department_id', 'role'),
        Index('idx_user_active_role', 'is_active', 'role'),
        Index('idx_user_department_active', 'department_id', 'is_active'),
    )
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
    doctor_room = db.Column(db.String(50), nullable=True)
    is_active = db.Column(db.Boolean, default=True, index=True)
    is_admin = db.Column(db.Boolean, default=False, index=True)
    digital_signature = db.Column(db.Text, nullable=True)

    last_login = db.Column(db.DateTime, nullable=True)
    session_version = db.Column(db.Integer, default=0, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=db.func.now(), nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now(), nullable=False, index=True)

    tenant = db.relationship('Tenant', back_populates='users', foreign_keys='User.tenant_id')

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
        lazy='selectin'
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
    
    # الإشعارات
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

    # علاقات النسخ الاحتياطي
    created_backups = db.relationship(
        'Backup',
        foreign_keys='Backup.created_by',
        back_populates='creator',
        lazy='selectin'
    )

    restored_backups = db.relationship(
        'Backup',
        foreign_keys='Backup.last_restore_by',
        back_populates='last_restore_user',
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
        lazy='selectin'
    )
    

    # علاقات إدارة الملفات
    uploaded_files = db.relationship(
        'FileUpload',
        foreign_keys='FileUpload.uploaded_by',
        back_populates='uploader',
        lazy='selectin'
    )
    file_permissions = db.relationship(
        'FilePermission',
        foreign_keys='FilePermission.user_id',
        back_populates='user',
        lazy='selectin'
    )
    granted_file_permissions = db.relationship(
        'FilePermission',
        foreign_keys='FilePermission.granted_by',
        back_populates='granter',
        lazy='selectin'
    )
    created_file_categories = db.relationship(
        'FileCategory',
        foreign_keys='FileCategory.created_by',
        back_populates='creator',
        lazy='selectin'
    )

    # علاقات إدارة المهام والمشاريع
    assigned_tasks = db.relationship(
        'Task',
        foreign_keys='Task.assigned_to',
        back_populates='assignee',
        lazy='selectin'
    )
    created_tasks = db.relationship(
        'Task',
        foreign_keys='Task.assigned_by',
        back_populates='assigner',
        lazy='selectin'
    )
    task_comments = db.relationship(
        'TaskComment',
        foreign_keys='TaskComment.user_id',
        back_populates='user',
        lazy='selectin'
    )
    task_attachments = db.relationship(
        'TaskAttachment',
        foreign_keys='TaskAttachment.attached_by',
        back_populates='attacher',
        lazy='selectin'
    )
    managed_projects = db.relationship(
        'Project',
        foreign_keys='Project.project_manager',
        back_populates='manager',
        lazy='selectin'
    )
    created_projects = db.relationship(
        'Project',
        foreign_keys='Project.created_by',
        back_populates='creator',
        lazy='selectin'
    )
    project_tasks = db.relationship(
        'ProjectTask',
        foreign_keys='ProjectTask.added_by',
        back_populates='adder',
        lazy='selectin'
    )
    project_memberships = db.relationship(
        'ProjectMember',
        foreign_keys='ProjectMember.user_id',
        back_populates='user',
        lazy='selectin'
    )
    added_project_members = db.relationship(
        'ProjectMember',
        foreign_keys='ProjectMember.added_by',
        back_populates='adder',
        lazy='selectin'
    )

    # Extended relationships (moved from dead code inside get_id())
    schedules = db.relationship('StaffWorkSchedule', back_populates='user', cascade='all, delete-orphan', lazy='selectin')
    absences = db.relationship('StaffAbsence', back_populates='user', cascade='all, delete-orphan', lazy='selectin')
    prescriptions = db.relationship('Prescription', back_populates='doctor', foreign_keys='Prescription.doctor_id', lazy='selectin')
    signed_medical_reports = db.relationship('MedicalReport', back_populates='signer', foreign_keys='MedicalReport.signed_by', lazy='selectin')
    digital_signatures = db.relationship('DigitalSignature', back_populates='user', lazy='selectin')
    session_logs = db.relationship('SessionLog', back_populates='user', lazy='selectin')
    nurse_profile = db.relationship('Nurse', back_populates='user', lazy='selectin')
    sent_whatsapp_messages = db.relationship('WhatsAppMessage', back_populates='sent_by_user', lazy='selectin')
    workflow_transfers = db.relationship('WorkflowTransfer', back_populates='transferred_by_user', lazy='selectin')
    workflow_events = db.relationship('VisitWorkflowEvent', back_populates='performer', lazy='selectin')

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        v = int(self.session_version or 0)
        return f"{self.id}:{v}"























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
            "digital_signature": self.digital_signature,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "session_version": int(self.session_version or 0),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def get_role_display(self) -> str:
        role_map = {
            'admin': 'مدير النظام',
            'manager': 'مدير',
            'doctor': 'طبيب',
            'nurse': 'ممرض',
            'reception': 'استقبال',
            'lab': 'مختبر',
            'radiology': 'أشعة',
            'accountant': 'محاسب',
            'emergency': 'طوارئ',
            'super_admin': 'مدير أعلى',
            'user': 'مستخدم',
            'pharmacist': 'صيدلي',
            'technician': 'فني',
            'receptionist': 'استقبال',
            'lab_tech': 'فني مختبر',
            'owner': 'مالك',
        }
        return role_map.get(self.role, self.role)

    def is_admin_user(self) -> bool:
        return bool(self.is_admin or self.role in ('admin', 'super_admin', 'manager'))

    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission via PermissionService"""
        try:
            from app.core.permission.service import PermissionService
            return PermissionService.has_permission(self, permission)
        except Exception:
            return False

    @db.validates('email')
    def validate_email(self, key, value):
        if value and '@' not in value:
            raise ValueError(f"البريد الإلكتروني غير صالح: {value}")
        return value

    @db.validates('phone')
    def validate_phone(self, key, value):
        if value is not None:
            cleaned = ''.join(c for c in value if c.isdigit() or c in '+-() ')
            if len(cleaned) < 7:
                raise ValueError(f"رقم الهاتف قصير جداً: {value}")
            return cleaned
        return value


class StaffWorkSchedule(TenantMixin, db.Model):
    __tablename__ = 'staff_work_schedules'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    day_of_week = db.Column(db.Integer, nullable=False, index=True)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    is_active = db.Column(db.Boolean, default=True, index=True)
    created_at = db.Column(db.DateTime, default=db.func.now(), nullable=False, index=True)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'day_of_week', name='uq_staff_schedule_user_day'),
    )

    user = db.relationship('User', back_populates='schedules')


class StaffAbsence(TenantMixin, db.Model):
    __tablename__ = 'staff_absences'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    start_date = db.Column(db.Date, nullable=False, index=True)
    end_date = db.Column(db.Date, nullable=False, index=True)
    reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    user = db.relationship('User', back_populates='absences')


@event.listens_for(User, 'after_insert')
def _create_default_schedule(mapper, connection, target):
    try:
        if target.role in ('doctor', 'lab', 'radiology'):
            tbl = StaffWorkSchedule.__table__
            default_days = [0, 1, 2, 3, 4]
            for d in default_days:
                connection.execute(
                    tbl.insert().values(
                        user_id=target.id,
                        tenant_id=target.tenant_id,
                        day_of_week=d,
                        start_time=time(9, 0),
                        end_time=time(17, 0),
                        is_active=True,
                        created_at=datetime.now(timezone.utc),
                    )
                )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Failed to create default schedule for user %s: %s", target.id, exc)
