"""
نموذج العلاج - Treatment Model
Medical System Treatment Model
"""

from datetime import datetime
from sqlalchemy import Index, CheckConstraint
from app_factory import db

class Treatment(db.Model):
    """نموذج العلاج"""
    
    __tablename__ = 'treatments'
    
    id = db.Column(db.Integer, primary_key=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # الأعراض
    symptoms = db.Column(db.Text, nullable=True)
    
    # الفحص السريري
    blood_pressure = db.Column(db.String(50), nullable=True)
    pulse = db.Column(db.String(50), nullable=True)
    temperature = db.Column(db.String(50), nullable=True)
    weight = db.Column(db.String(50), nullable=True)
    examination_results = db.Column(db.Text, nullable=True)
    
    # التشخيص
    primary_diagnosis = db.Column(db.String(500), nullable=False)
    secondary_diagnosis = db.Column(db.String(500), nullable=True)
    diagnosis_notes = db.Column(db.Text, nullable=True)
    
    # العلاج
    treatment_plan = db.Column(db.Text, nullable=True)
    
    # المتابعة
    follow_up_date = db.Column(db.Date, nullable=True)
    follow_up_instructions = db.Column(db.Text, nullable=True)
    
    # الفحوصات المطلوبة
    requested_labs = db.Column(db.Text, nullable=True)
    requested_radiology = db.Column(db.Text, nullable=True)
    
    # الحالة
    status = db.Column(db.String(50), default='pending')  # pending, completed, follow_up
    
    # التواريخ
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Constraints and Indexes
    __table_args__ = (
        CheckConstraint("status IN ('active', 'completed', 'cancelled', 'suspended')", name='chk_treatment_status'),
        CheckConstraint("visit_id > 0", name='chk_treatment_visit_id'),
        Index('idx_treatment_visit', 'visit_id'),
        Index('idx_treatment_doctor', 'doctor_id'),
        Index('idx_treatment_status', 'status'),
        Index('idx_treatment_created', 'created_at'),
    )
    
    # العلاقات
    visit = db.relationship('Visit', back_populates='treatments')
    doctor = db.relationship('User', foreign_keys=[doctor_id])
    
    def __repr__(self):
        return f'<Treatment {self.id} - {self.primary_diagnosis}>'
    
    def get_status_display(self):
        """حالة العلاج للعرض"""
        status_map = {
            'pending': 'معلق',
            'completed': 'مكتمل',
            'follow_up': 'متابعة'
        }
        return status_map.get(self.status, self.status)
    
    def get_status_color(self):
        """لون الحالة"""
        color_map = {
            'pending': 'warning',
            'completed': 'success',
            'follow_up': 'info'
        }
        return color_map.get(self.status, 'secondary')
    
    def is_completed(self):
        """هل تم إكمال العلاج"""
        return self.status == 'completed'
    
    def is_pending(self):
        """هل العلاج معلق"""
        return self.status == 'pending'
    
    def is_follow_up(self):
        """هل العلاج يحتاج متابعة"""
        return self.status == 'follow_up'
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'visit_id': self.visit_id,
            'doctor_id': self.doctor_id,
            'doctor_name': self.doctor.full_name if self.doctor else None,
            'symptoms': self.symptoms,
            'blood_pressure': self.blood_pressure,
            'pulse': self.pulse,
            'temperature': self.temperature,
            'weight': self.weight,
            'examination_results': self.examination_results,
            'primary_diagnosis': self.primary_diagnosis,
            'secondary_diagnosis': self.secondary_diagnosis,
            'diagnosis_notes': self.diagnosis_notes,
            'treatment_plan': self.treatment_plan,
            'follow_up_date': self.follow_up_date.isoformat() if self.follow_up_date else None,
            'follow_up_instructions': self.follow_up_instructions,
            'requested_labs': self.requested_labs,
            'requested_radiology': self.requested_radiology,
            'status': self.status,
            'status_display': self.get_status_display(),
            'status_color': self.get_status_color(),
            'is_completed': self.is_completed(),
            'is_pending': self.is_pending(),
            'is_follow_up': self.is_follow_up(),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
