"""
نموذج إدارة التدفق - Workflow Models
Medical System Workflow Models
"""

from datetime import datetime, timezone
from app_factory import db
from app.shared.mixins import TenantMixin

class WorkflowStep(TenantMixin, db.Model):
    """نموذج خطوة التدفق"""
    
    __tablename__ = 'workflow_steps'
    __tenant_migration__ = True
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    name_ar = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    step_type = db.Column(db.String(50), nullable=False)  # reception, doctor, lab, radiology, pharmacy, billing
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True, index=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # العلاقات
    department = db.relationship('Department', back_populates='workflow_steps')
    patient_workflows = db.relationship('PatientWorkflow', back_populates='current_step')
    transfers_from = db.relationship('WorkflowTransfer', foreign_keys='WorkflowTransfer.from_step_id', back_populates='from_step')
    transfers_to = db.relationship('WorkflowTransfer', foreign_keys='WorkflowTransfer.to_step_id', back_populates='to_step')
    workflow_queue_items = db.relationship('WorkflowQueue', back_populates='step')




    
    def __repr__(self):
        return f'<WorkflowStep {self.name_ar}>'
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'name': self.name,
            'name_ar': self.name_ar,
            'description': self.description,
            'step_type': self.step_type,
            'department_id': self.department_id,
            'department_name': self.department.name_ar if self.department else None,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class PatientWorkflow(TenantMixin, db.Model):
    """نموذج تدفق المريض"""
    
    __tablename__ = 'patient_workflows'
    __tenant_migration__ = True
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='RESTRICT'), nullable=False, index=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='SET NULL'), nullable=True, index=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.id', ondelete='SET NULL'), nullable=True, index=True)
    
    # معلومات التدفق
    current_step_id = db.Column(db.Integer, db.ForeignKey('workflow_steps.id', ondelete='RESTRICT'), nullable=False, index=True)
    status = db.Column(db.String(20), default='active')  # active, completed, cancelled, transferred
    priority = db.Column(db.String(20), default='normal')  # low, normal, high, urgent
    
    # معلومات إضافية
    notes = db.Column(db.Text, nullable=True)
    estimated_duration = db.Column(db.Integer, default=30)  # بالدقائق
    actual_duration = db.Column(db.Integer, nullable=True)  # بالدقائق
    
    # تواريخ
    started_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # العلاقات
    patient = db.relationship('Patient', back_populates='workflows')
    visit = db.relationship('Visit', back_populates='workflows')
    appointment = db.relationship('Appointment', back_populates='workflows')
    current_step = db.relationship('WorkflowStep', back_populates='patient_workflows')
    transfers = db.relationship('WorkflowTransfer', back_populates='workflow')
    workflow_queue_items = db.relationship('WorkflowQueue', back_populates='workflow')


    
    def __repr__(self):
        return f'<PatientWorkflow {self.id}: {self.patient.full_name}>'
    
    def get_status_display(self):
        """حالة التدفق للعرض"""
        status_map = {
            'active': 'نشط',
            'completed': 'مكتمل',
            'cancelled': 'ملغي',
            'transferred': 'منقول'
        }
        return status_map.get(self.status, 'غير محدد')
    
    def get_priority_display(self):
        """أولوية التدفق للعرض"""
        priority_map = {
            'low': 'منخفضة',
            'normal': 'عادية',
            'high': 'عالية',
            'urgent': 'عاجلة'
        }
        return priority_map.get(self.priority, 'غير محددة')
    
    def get_priority_color(self):
        """لون الأولوية"""
        color_map = {
            'low': 'success',
            'normal': 'primary',
            'high': 'warning',
            'urgent': 'danger'
        }
        return color_map.get(self.priority, 'secondary')
    
    def is_completed(self):
        """هل تم إكمال التدفق"""
        return self.status == 'completed'
    
    def is_active(self):
        """هل التدفق نشط"""
        return self.status == 'active'
    
    def can_transfer(self):
        """هل يمكن نقل التدفق"""
        return self.status == 'active'
    
    def get_duration(self):
        """مدة التدفق"""
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds() / 60
        else:
            return (datetime.now(timezone.utc) - self.started_at).total_seconds() / 60
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'patient_name': self.patient.full_name,
            'visit_id': self.visit_id,
            'appointment_id': self.appointment_id,
            'current_step_id': self.current_step_id,
            'current_step_name': self.current_step.name_ar if self.current_step else None,
            'status': self.status,
            'status_display': self.get_status_display(),
            'priority': self.priority,
            'priority_display': self.get_priority_display(),
            'priority_color': self.get_priority_color(),
            'notes': self.notes,
            'estimated_duration': self.estimated_duration,
            'actual_duration': self.actual_duration,
            'duration': self.get_duration(),
            'is_completed': self.is_completed(),
            'is_active': self.is_active(),
            'can_transfer': self.can_transfer(),
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class WorkflowTransfer(TenantMixin, db.Model):
    """نموذج نقل التدفق"""
    
    __tablename__ = 'workflow_transfers'
    
    id = db.Column(db.Integer, primary_key=True)
    workflow_id = db.Column(db.Integer, db.ForeignKey('patient_workflows.id', ondelete='CASCADE'), nullable=False, index=True)
    from_step_id = db.Column(db.Integer, db.ForeignKey('workflow_steps.id', ondelete='SET NULL'), nullable=True, index=True)
    to_step_id = db.Column(db.Integer, db.ForeignKey('workflow_steps.id', ondelete='SET NULL'), nullable=True, index=True)
    
    # معلومات النقل
    reason = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    transferred_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    
    # تواريخ
    transferred_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # العلاقات
    workflow = db.relationship('PatientWorkflow', back_populates='transfers')
    from_step = db.relationship('WorkflowStep', foreign_keys=[from_step_id], back_populates='transfers_from')
    to_step = db.relationship('WorkflowStep', foreign_keys=[to_step_id], back_populates='transfers_to')
    transferred_by_user = db.relationship('User', back_populates='workflow_transfers')
    
    def __repr__(self):
        return f'<WorkflowTransfer {self.id}: {self.from_step.name_ar} -> {self.to_step.name_ar}>'
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'workflow_id': self.workflow_id,
            'from_step_id': self.from_step_id,
            'from_step_name': self.from_step.name_ar if self.from_step else None,
            'to_step_id': self.to_step_id,
            'to_step_name': self.to_step.name_ar if self.to_step else None,
            'reason': self.reason,
            'notes': self.notes,
            'transferred_by': self.transferred_by,
            'transferred_by_name': self.transferred_by_user.full_name if self.transferred_by_user else None,
            'transferred_at': self.transferred_at.isoformat(),
            'created_at': self.created_at.isoformat()
        }

class WorkflowQueue(TenantMixin, db.Model):
    """نموذج طابور التدفق"""
    
    __tablename__ = 'workflow_queues'
    
    id = db.Column(db.Integer, primary_key=True)
    step_id = db.Column(db.Integer, db.ForeignKey('workflow_steps.id', ondelete='CASCADE'), nullable=False, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='RESTRICT'), nullable=False, index=True)
    workflow_id = db.Column(db.Integer, db.ForeignKey('patient_workflows.id', ondelete='CASCADE'), nullable=False, index=True)
    
    # معلومات الطابور
    queue_number = db.Column(db.Integer, nullable=False)
    estimated_wait_time = db.Column(db.Integer, default=30)  # بالدقائق
    actual_wait_time = db.Column(db.Integer, nullable=True)  # بالدقائق
    status = db.Column(db.String(20), default='waiting')  # waiting, called, in_progress, completed
    
    # تواريخ
    queued_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    called_at = db.Column(db.DateTime, nullable=True)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # العلاقات
    step = db.relationship('WorkflowStep', back_populates='workflow_queue_items')
    patient = db.relationship('Patient', back_populates='workflow_queue_items')
    workflow = db.relationship('PatientWorkflow', back_populates='workflow_queue_items')
    
    def __repr__(self):
        return f'<WorkflowQueue {self.id}: {self.patient.full_name} - {self.step.name_ar}>'
    
    def get_status_display(self):
        """حالة الطابور للعرض"""
        status_map = {
            'waiting': 'في الانتظار',
            'called': 'تم الاستدعاء',
            'in_progress': 'قيد التنفيذ',
            'completed': 'مكتمل'
        }
        return status_map.get(self.status, 'غير محدد')
    
    def get_status_color(self):
        """لون الحالة"""
        color_map = {
            'waiting': 'warning',
            'called': 'info',
            'in_progress': 'primary',
            'completed': 'success'
        }
        return color_map.get(self.status, 'secondary')
    
    def get_wait_time(self):
        """وقت الانتظار"""
        if self.completed_at:
            return (self.completed_at - self.queued_at).total_seconds() / 60
        elif self.started_at:
            return (self.started_at - self.queued_at).total_seconds() / 60
        else:
            return (datetime.now(timezone.utc) - self.queued_at).total_seconds() / 60
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'step_id': self.step_id,
            'step_name': self.step.name_ar if self.step else None,
            'patient_id': self.patient_id,
            'patient_name': self.patient.full_name,
            'workflow_id': self.workflow_id,
            'queue_number': self.queue_number,
            'estimated_wait_time': self.estimated_wait_time,
            'actual_wait_time': self.actual_wait_time,
            'wait_time': self.get_wait_time(),
            'status': self.status,
            'status_display': self.get_status_display(),
            'status_color': self.get_status_color(),
            'queued_at': self.queued_at.isoformat(),
            'called_at': self.called_at.isoformat() if self.called_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }


class VisitWorkflowEvent(TenantMixin, db.Model):
    """Event log for visit state transitions."""
    __tablename__ = 'visit_workflow_events'
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='RESTRICT'), nullable=False, index=True)
    from_status = db.Column(db.String(50), nullable=True)
    to_status = db.Column(db.String(50), nullable=False)
    performed_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    visit = db.relationship('Visit', back_populates='workflow_events')
    performer = db.relationship('User', back_populates='workflow_events')

    def __repr__(self):
        return f'<VisitWorkflowEvent {self.id}: {self.from_status} -> {self.to_status}>'
