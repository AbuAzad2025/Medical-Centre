"""
نموذج إدارة الطابور - Queue Management Model
Medical System Queue Management Model
"""

from datetime import datetime, timezone
from app_factory import db
import json

class QueueManagement(db.Model):
    """نموذج إدارة الطابور"""
    
    __tablename__ = 'queue_management'
    
    id = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id'), nullable=True)
    
    # معلومات الطابور
    queue_number = db.Column(db.String(20), nullable=False)
    priority_level = db.Column(db.String(20), default='normal')  # low, normal, high, urgent
    status = db.Column(db.String(20), default='waiting')  # waiting, called, in_progress, completed, cancelled
    
    # معلومات الدفع
    payment_status = db.Column(db.String(20), default='pending')  # pending, paid, partial, waived
    payment_amount = db.Column(db.Numeric(12, 2), default=0.0)
    payment_method = db.Column(db.String(50), nullable=True)
    estimated_wait_time = db.Column(db.Integer, default=30)
    
    # معلومات الطوارئ
    is_emergency = db.Column(db.Boolean, default=False)
    emergency_reason = db.Column(db.Text, nullable=True)
    emergency_approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # معلومات الدخول القوي
    force_entry = db.Column(db.Boolean, default=False)
    force_entry_reason = db.Column(db.Text, nullable=True)
    force_entry_approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # التوقيت
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    queued_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    called_at = db.Column(db.DateTime, nullable=True)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # ملاحظات
    notes = db.Column(db.Text, nullable=True)
    
    # العلاقات
    department = db.relationship('Department', backref='queue_items')
    patient = db.relationship('Patient', backref='queue_items')
    visit = db.relationship('Visit', backref='queue_items')
    emergency_approver = db.relationship('User', foreign_keys=[emergency_approved_by], backref='emergency_approvals')
    force_entry_approver = db.relationship('User', foreign_keys=[force_entry_approved_by], backref='force_entry_approvals')
    
    def __repr__(self):
        return f'<QueueManagement {self.queue_number} - {self.patient.full_name if self.patient else "Unknown"}>'
    
    def get_priority_display(self):
        """أولوية الطابور للعرض"""
        priority_map = {
            'low': 'منخفضة',
            'normal': 'عادية',
            'high': 'عالية',
            'urgent': 'عاجلة'
        }
        return priority_map.get(self.priority_level, self.priority_level)
    
    def get_status_display(self):
        """حالة الطابور للعرض"""
        status_map = {
            'waiting': 'في الانتظار',
            'called': 'تم الاستدعاء',
            'in_progress': 'قيد التنفيذ',
            'completed': 'مكتمل',
            'skipped': 'تم التخطي',
            'cancelled': 'ملغي'
        }
        return status_map.get(self.status, self.status)
    
    def get_payment_status_display(self):
        """حالة الدفع للعرض"""
        status_map = {
            'pending': 'معلق',
            'paid': 'مدفوع',
            'partial': 'جزئي',
            'waived': 'معفى'
        }
        return status_map.get(self.payment_status, self.payment_status)
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'department_id': self.department_id,
            'patient_id': self.patient_id,
            'visit_id': self.visit_id,
            'queue_number': self.queue_number,
            'priority_level': self.priority_level,
            'status': self.status,
            'payment_status': self.payment_status,
            'payment_amount': self.payment_amount,
            'payment_method': self.payment_method,
            'is_emergency': self.is_emergency,
            'emergency_reason': self.emergency_reason,
            'emergency_approved_by': self.emergency_approved_by,
            'force_entry': self.force_entry,
            'force_entry_reason': self.force_entry_reason,
            'force_entry_approved_by': self.force_entry_approved_by,
            'queued_at': self.queued_at.isoformat() if self.queued_at else None,
            'called_at': self.called_at.isoformat() if self.called_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'notes': self.notes
        }

class QueueSettings(db.Model):
    """نموذج إعدادات الطابور"""
    
    __tablename__ = 'queue_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=False)
    
    # إعدادات الطابور
    max_queue_size = db.Column(db.Integer, default=50)
    average_wait_time = db.Column(db.Integer, default=30)  # بالدقائق
    emergency_priority = db.Column(db.Boolean, default=True)
    force_entry_allowed = db.Column(db.Boolean, default=True)
    
    # إعدادات الدفع
    payment_required = db.Column(db.Boolean, default=True)
    payment_amount = db.Column(db.Numeric(12, 2), default=0.0)
    emergency_payment_waived = db.Column(db.Boolean, default=True)
    allow_partial_payment = db.Column(db.Boolean, default=True)
    allow_debt = db.Column(db.Boolean, default=False)
    
    # إعدادات الإشعارات
    auto_notifications = db.Column(db.Boolean, default=True)
    notification_interval = db.Column(db.Integer, default=15)  # بالدقائق
    
    # التوقيت
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # العلاقات
    department = db.relationship('Department', backref='queue_settings')
    
    def __repr__(self):
        return f'<QueueSettings for {self.department.name if self.department else "Unknown"}>'
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'department_id': self.department_id,
            'max_queue_size': self.max_queue_size,
            'average_wait_time': self.average_wait_time,
            'emergency_priority': self.emergency_priority,
            'force_entry_allowed': self.force_entry_allowed,
            'payment_required': self.payment_required,
            'payment_amount': self.payment_amount,
            'emergency_payment_waived': self.emergency_payment_waived,
            'allow_partial_payment': self.allow_partial_payment,
            'allow_debt': self.allow_debt,
            'auto_notifications': self.auto_notifications,
            'notification_interval': self.notification_interval,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
