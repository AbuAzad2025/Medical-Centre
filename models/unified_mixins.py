"""
النماذج الموحدة - Unified Mixins
Medical System Unified Mixins
"""

from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, String, Boolean, Text, ForeignKey, Index
from sqlalchemy.ext.declarative import declared_attr
from app_factory import db

class BaseModelMixin:
    """الخلطة الأساسية لجميع النماذج"""
    
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, index=True)
    
    def to_dict(self):
        """تحويل النموذج إلى قاموس بشكل ذكي"""
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            if isinstance(value, datetime):
                result[column.name] = value.isoformat()
            else:
                result[column.name] = value
        return result

class StatusMixin:
    """خلطة الحالة الموحدة"""
    
    status = Column(String(50), nullable=False, default='ACTIVE', index=True)
    
    # قواميس الحالة الموحدة
    STATUS_CHOICES = {
        'ACTIVE': {'display': 'نشط', 'color': 'success'},
        'INACTIVE': {'display': 'غير نشط', 'color': 'secondary'},
        'PENDING': {'display': 'في الانتظار', 'color': 'warning'},
        'COMPLETED': {'display': 'مكتمل', 'color': 'success'},
        'CANCELLED': {'display': 'ملغي', 'color': 'danger'},
        'IN_PROGRESS': {'display': 'قيد التنفيذ', 'color': 'info'},
        'READY': {'display': 'جاهز', 'color': 'primary'},
        'ARCHIVED': {'display': 'مؤرشف', 'color': 'dark'}
    }
    
    def get_status_display(self):
        """الحصول على عرض الحالة"""
        return self.STATUS_CHOICES.get(self.status, {}).get('display', self.status)
    
    def get_status_color(self):
        """الحصول على لون الحالة"""
        return self.STATUS_CHOICES.get(self.status, {}).get('color', 'secondary')
    
    def is_active(self):
        """هل النموذج نشط"""
        return self.status == 'ACTIVE'
    
    def is_completed(self):
        """هل النموذج مكتمل"""
        return self.status == 'COMPLETED'

class MedicalEntityMixin:
    """خلطة الكيانات الطبية"""
    
    patient_id = Column(Integer, ForeignKey('patients.id'), nullable=False, index=True)
    visit_id = Column(Integer, ForeignKey('visits.id'), nullable=True, index=True)
    doctor_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    
    # العلاقات الأساسية
    @declared_attr
    def patient(cls):
        return db.relationship('Patient', lazy='select')
    
    @declared_attr
    def visit(cls):
        return db.relationship('Visit', lazy='select')
    
    @declared_attr
    def doctor(cls):
        return db.relationship('User', foreign_keys=[cls.doctor_id], lazy='select')

class AuditBase(BaseModelMixin):
    """قاعدة التدقيق الموحدة"""
    
    entity_type = Column(String(100), nullable=False, index=True)
    entity_id = Column(Integer, nullable=False, index=True)
    action = Column(String(50), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    user_ip = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    old_values = Column(Text, nullable=True)  # JSON string
    new_values = Column(Text, nullable=True)  # JSON string
    description = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    
    # العلاقات
    user = db.relationship('User', lazy='select')
    
    # فهارس مركبة
    __table_args__ = (
        Index('idx_audit_entity', 'entity_type', 'entity_id'),
        Index('idx_audit_action', 'action'),
        Index('idx_audit_user', 'user_id'),
    )

class PermissionBase(BaseModelMixin):
    """قاعدة الصلاحيات الموحدة"""
    
    permission_name = Column(String(100), nullable=False, index=True)
    permission_value = Column(String(200), nullable=True)
    is_granted = Column(Boolean, default=True, index=True)
    granted_by = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    granted_at = Column(DateTime, default=datetime.utcnow, index=True)
    expires_at = Column(DateTime, nullable=True, index=True)
    reason = Column(Text, nullable=True)
    
    # العلاقات
    granter = db.relationship('User', foreign_keys=[granted_by], lazy='select')
    
    def is_expired(self):
        """هل انتهت صلاحية الصلاحية"""
        if self.expires_at:
            return datetime.utcnow() > self.expires_at
        return False

class FinancialBase(BaseModelMixin, StatusMixin):
    """قاعدة المعاملات المالية الموحدة"""
    
    amount = Column(db.Float, nullable=False, index=True)
    currency = Column(String(10), default='EGP', nullable=False)
    payment_method = Column(String(50), nullable=False, index=True)
    payment_status = Column(String(50), nullable=False, default='PENDING', index=True)
    transaction_type = Column(String(50), nullable=False, index=True)  # INCOME, EXPENSE, REFUND
    reference_number = Column(String(100), nullable=True, index=True)
    description = Column(Text, nullable=True)
    reason = Column(String(200), nullable=True)
    
    # العلاقات المالية
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey('patients.id'), nullable=True, index=True)
    visit_id = Column(Integer, ForeignKey('visits.id'), nullable=True, index=True)
    invoice_id = Column(Integer, ForeignKey('invoices.id'), nullable=True, index=True)
    
    # العلاقات
    user = db.relationship('User', foreign_keys=[user_id], lazy='select')
    patient = db.relationship('Patient', lazy='select')
    visit = db.relationship('Visit', lazy='select')
    invoice = db.relationship('Invoice', lazy='select')
    
    # فهارس مركبة
    __table_args__ = (
        Index('idx_financial_user', 'user_id'),
        Index('idx_financial_patient', 'patient_id'),
        Index('idx_financial_visit', 'visit_id'),
        Index('idx_financial_type', 'transaction_type'),
        Index('idx_financial_status', 'payment_status'),
    )
    
    def get_amount_display(self):
        """عرض المبلغ مع العملة"""
        return f"{self.amount} {self.currency}"
    
    def is_paid(self):
        """هل تم الدفع"""
        return self.payment_status == 'PAID'
    
    def is_pending(self):
        """هل في الانتظار"""
        return self.payment_status == 'PENDING'

class FileBase(BaseModelMixin, StatusMixin):
    """قاعدة الملفات الموحدة"""
    
    filename = Column(String(255), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False, index=True)
    mime_type = Column(String(100), nullable=False)
    file_hash = Column(String(64), nullable=True, index=True)
    
    # العلاقات
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey('file_categories.id'), nullable=True, index=True)
    
    user = db.relationship('User', lazy='select')
    category = db.relationship('FileCategory', lazy='select')
    
    def get_size_display(self):
        """عرض حجم الملف"""
        size = self.file_size
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

class NotificationBase(BaseModelMixin, StatusMixin):
    """قاعدة الإشعارات الموحدة"""
    
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(String(50), nullable=False, index=True)
    priority = Column(String(20), default='NORMAL', nullable=False, index=True)
    
    # العلاقات
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    sender_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    
    user = db.relationship('User', foreign_keys=[user_id], lazy='select')
    sender = db.relationship('User', foreign_keys=[sender_id], lazy='select')
    
    # فهارس مركبة
    __table_args__ = (
        Index('idx_notification_user', 'user_id'),
        Index('idx_notification_type', 'notification_type'),
        Index('idx_notification_priority', 'priority'),
    )
    
    def get_priority_color(self):
        """لون الأولوية"""
        colors = {
            'LOW': 'secondary',
            'NORMAL': 'primary',
            'HIGH': 'warning',
            'URGENT': 'danger'
        }
        return colors.get(self.priority, 'primary')