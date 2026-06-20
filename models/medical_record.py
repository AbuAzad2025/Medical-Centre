"""
السجل الطبي - MedicalRecord (ملاحظات عامة للمريض)
"""
from datetime import datetime, timezone
from sqlalchemy import Index
from app_factory import db
from app.shared.mixins import TenantMixin


class MedicalRecord(TenantMixin, db.Model):
    __tablename__ = 'medical_records'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False, index=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='CASCADE'), nullable=True, index=True)
    title = db.Column(db.String(120), nullable=False)
    details = db.Column(db.Text, nullable=True)
    diagnosis = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    __table_args__ = (
        Index('idx_med_record_patient_created', 'patient_id', 'created_at'),
        Index('idx_med_record_visit_created', 'visit_id', 'created_at'),
    )

    patient = db.relationship('Patient', back_populates='medical_records', lazy='selectin')
    visit = db.relationship('Visit', back_populates='medical_records', foreign_keys=[visit_id])
    creator = db.relationship('User', foreign_keys=[created_by], lazy='selectin')
    coded_diagnoses = db.relationship('CodedDiagnosis', back_populates='medical_record')


    def __repr__(self) -> str:
        return f"<MedicalRecord {self.title}>"
