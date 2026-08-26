"""
نموذج حالات الطوارئ - Emergency Cases Model
Medical System Emergency Cases
"""

from datetime import UTC, datetime

from sqlalchemy import Index

from app.shared.enums import EmergencyStatus
from app.shared.mixins import TenantMixin
from app_factory import db


class EmergencyCase(TenantMixin, db.Model):
    """نموذج حالات الطوارئ"""

    __tablename__ = 'emergency_cases'
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(
        db.Integer, db.ForeignKey('patients.id', ondelete='RESTRICT'), nullable=False, index=True
    )
    visit_id = db.Column(
        db.Integer, db.ForeignKey('visits.id', ondelete='SET NULL'), nullable=True, index=True
    )
    case_number = db.Column(db.String(50), unique=True, nullable=False)
    chief_complaint = db.Column(db.Text, nullable=False)
    severity = db.Column(
        db.String(20), nullable=False, default='MODERATE'
    )  # LOW, MODERATE, HIGH, CRITICAL
    triage_notes = db.Column(db.Text, nullable=True)
    vital_signs = db.Column(db.Text, nullable=True)  # JSON string for vital signs
    diagnosis = db.Column(db.Text, nullable=True)
    treatment_plan = db.Column(db.Text, nullable=True)
    status = db.Column(
        db.String(50), nullable=False, index=True, server_default=EmergencyStatus.IN_PROGRESS.value
    )
    completed_at = db.Column(db.DateTime, nullable=True, index=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(UTC), index=True
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        index=True,
    )
    lab_request_id = db.Column(
        db.Integer, db.ForeignKey('lab_requests.id', ondelete='SET NULL'), nullable=True, index=True
    )
    radiology_request_id = db.Column(
        db.Integer,
        db.ForeignKey('radiology_requests.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    treatment_given = db.Column(db.Text, nullable=True)
    medications_text = db.Column(db.Text, nullable=True)
    procedures_text = db.Column(db.Text, nullable=True)
    treated_by_id = db.Column(
        db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True
    )
    treatment_started_at = db.Column(db.DateTime, nullable=True)
    treatment_completed_at = db.Column(db.DateTime, nullable=True)
    completed_by_id = db.Column(
        db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True
    )

    __table_args__ = (
        Index('idx_emergency_patient_status', 'patient_id', 'status'),
        Index('idx_emergency_severity_created', 'severity', 'created_at'),
    )

    # العلاقات
    patient = db.relationship('Patient', back_populates='emergency_cases', lazy='selectin')
    visit = db.relationship('Visit', back_populates='emergency_cases', lazy='selectin')
    status_history = db.relationship(
        'EmergencyStatusHistory', back_populates='emergency', lazy='selectin'
    )

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
        val = (value or '').upper().strip()
        priority_map = {
            'CRITICAL': 'CRITICAL',
            'URGENT': 'HIGH',
            'HIGH': 'HIGH',
            'NORMAL': 'MODERATE',
            'MODERATE': 'MODERATE',
            'MEDIUM': 'MODERATE',
            'LOW': 'LOW',
        }
        mapped = priority_map.get(val)
        if mapped:
            self.severity = mapped
        elif val:
            raise ValueError(f'قيمة الأولوية غير صالحة: {value}')

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
            'treatment_given': self.treatment_given,
            'medications_text': self.medications_text,
            'procedures_text': self.procedures_text,
            'treated_by_id': self.treated_by_id,
            'treatment_started_at': self.treatment_started_at.isoformat()
            if self.treatment_started_at
            else None,
            'treatment_completed_at': self.treatment_completed_at.isoformat()
            if self.treatment_completed_at
            else None,
            'completed_by_id': self.completed_by_id,
            'status': self.status,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }

    ALLOWED_SEVERITIES = {'LOW', 'MODERATE', 'HIGH', 'CRITICAL'}

    @db.validates('severity')
    def validate_severity(self, key, value):
        if value and value.upper() not in self.ALLOWED_SEVERITIES:
            raise ValueError(
                f'شدة الحالة غير صالحة: {value}. القيم المسموحة: {self.ALLOWED_SEVERITIES}'
            )
        return value.upper() if value else value
