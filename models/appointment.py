"""
نموذج الموعد - Appointment (نسخة نهائية)
"""
from datetime import datetime
from sqlalchemy import Index
from app_factory import db


class Appointment(db.Model):
    __tablename__ = 'appointments'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False, index=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    starts_at = db.Column(db.DateTime, nullable=False, index=True)
    ends_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='SCHEDULED', index=True)  # SCHEDULED|CONFIRMED|CANCELLED|NO_SHOW|DONE
    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (
        db.UniqueConstraint('patient_id', 'starts_at', name='uq_appointment_patient_time'),
        db.Index('idx_appt_doctor_time', 'doctor_id', 'starts_at'),
    )

    patient = db.relationship('Patient', back_populates='appointments', lazy='selectin')
    doctor = db.relationship('User', back_populates='doctor_appointments', foreign_keys=[doctor_id], lazy='selectin')
    department = db.relationship('Department', back_populates='appointments', lazy='selectin')
    creator = db.relationship('User', foreign_keys=[created_by], lazy='select')

    def __repr__(self) -> str:
        return f"<Appointment patient={self.patient_id} at={self.starts_at}>"