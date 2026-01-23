"""
نموذج حالات الطوارئ - Emergency Cases Model
Medical System Emergency Cases
"""

from datetime import datetime
from sqlalchemy import func
from app_factory import db

class EmergencyCase(db.Model):
    """نموذج حالات الطوارئ"""
    
    __tablename__ = 'emergency_cases'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id'), nullable=True)
    case_number = db.Column(db.String(50), unique=True, nullable=False)
    chief_complaint = db.Column(db.Text, nullable=False)
    severity = db.Column(db.String(20), nullable=False, default='MODERATE')  # LOW, MODERATE, HIGH, CRITICAL
    triage_notes = db.Column(db.Text, nullable=True)
    vital_signs = db.Column(db.Text, nullable=True)  # JSON string for vital signs
    diagnosis = db.Column(db.Text, nullable=True)
    treatment_plan = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), nullable=False, index=True, server_default="IN_PROGRESS")
    completed_at = db.Column(db.DateTime, nullable=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, server_default=func.now(), index=True)
    updated_at = db.Column(db.DateTime, nullable=False, server_default=func.now(), onupdate=func.now(), index=True)
    
    # العلاقات
    patient = db.relationship('Patient', backref='emergency_cases', lazy='select')
    visit = db.relationship('Visit', backref='emergency_cases', lazy='select')

    @property
    def priority(self):
        severity = (self.severity or '').upper()
        if severity == 'CRITICAL':
            return 'CRITICAL'
        if severity == 'HIGH':
            return 'URGENT'
        if severity == 'MODERATE':
            return 'NORMAL'
        if severity == 'LOW':
            return 'LOW'
        return None

    @priority.setter
    def priority(self, value):
        val = (value or '').upper()
        priority_map = {
            'CRITICAL': 'CRITICAL',
            'URGENT': 'HIGH',
            'HIGH': 'HIGH',
            'NORMAL': 'MODERATE',
            'MODERATE': 'MODERATE',
            'LOW': 'LOW'
        }
        mapped = priority_map.get(val)
        if mapped:
            self.severity = mapped
    
    def __repr__(self):
        return f'<EmergencyCase {self.case_number}>'
    
    def to_dict(self):
        """تحويل إلى قاموس"""
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'visit_id': self.visit_id,
            'case_number': self.case_number,
            'chief_complaint': self.chief_complaint,
            'severity': self.severity,
            'triage_notes': self.triage_notes,
            'vital_signs': self.vital_signs,
            'diagnosis': self.diagnosis,
            'treatment_plan': self.treatment_plan,
            'status': self.status,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
