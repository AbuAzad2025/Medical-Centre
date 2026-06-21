"""
نموذج سير عمل الطلبات - Request Workflow Model
Medical System Request Workflow Model
"""

from datetime import datetime, timezone
from app_factory import db
from app.shared.mixins import TenantMixin

class RequestWorkflow(TenantMixin, db.Model):
    """نموذج سير عمل الطلبات لجميع الأقسام"""
    
    __tablename__ = 'request_workflows'
    
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, nullable=False)
    request_type = db.Column(db.String(20), nullable=False)  # lab, radiology, emergency, doctor, pharmacy
    department = db.Column(db.String(50), nullable=False)  # Current department
    status = db.Column(db.String(50), nullable=False)  # Current status
    action = db.Column(db.String(100), nullable=False)  # Action taken
    notes = db.Column(db.Text, nullable=True)  # Additional notes
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    
    # معلومات إضافية
    priority = db.Column(db.String(20), default='normal')  # urgent, high, normal, low
    estimated_completion = db.Column(db.DateTime, nullable=True)  # وقت الإنجاز المتوقع
    actual_completion = db.Column(db.DateTime, nullable=True)  # وقت الإنجاز الفعلي
    next_department = db.Column(db.String(50), nullable=True)  # القسم التالي
    is_completed = db.Column(db.Boolean, default=False)  # هل تم إنجاز المهمة
    
    # العلاقات
    user = db.relationship('User')
    
    def __repr__(self):
        return f'<RequestWorkflow {self.request_type}_{self.request_id}_{self.department}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'request_id': self.request_id,
            'request_type': self.request_type,
            'department': self.department,
            'status': self.status,
            'action': self.action,
            'notes': self.notes,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'user_id': self.user_id,
            'priority': self.priority,
            'estimated_completion': self.estimated_completion.isoformat() if self.estimated_completion else None,
            'actual_completion': self.actual_completion.isoformat() if self.actual_completion else None,
            'next_department': self.next_department,
            'is_completed': self.is_completed
        }

class DepartmentWorkflow(TenantMixin, db.Model):
    """نموذج سير عمل الأقسام"""
    
    __tablename__ = 'department_workflows'
    
    id = db.Column(db.Integer, primary_key=True)
    department_name = db.Column(db.String(50), nullable=False, unique=True)
    department_name_ar = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)
    
    # إعدادات القسم
    default_processing_time = db.Column(db.Integer, default=30)  # دقائق
    requires_approval = db.Column(db.Boolean, default=False)
    can_auto_assign = db.Column(db.Boolean, default=True)
    notification_enabled = db.Column(db.Boolean, default=True)
    
    def __repr__(self):
        return f'<DepartmentWorkflow {self.department_name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'department_name': self.department_name,
            'department_name_ar': self.department_name_ar,
            'description': self.description,
            'is_active': self.is_active,
            'sort_order': self.sort_order,
            'default_processing_time': self.default_processing_time,
            'requires_approval': self.requires_approval,
            'can_auto_assign': self.can_auto_assign,
            'notification_enabled': self.notification_enabled
        }
