"""
نموذج الموعد - Appointment (نسخة نهائية)
"""
from datetime import datetime, timezone
from sqlalchemy import Index
from app_factory import db
from app.shared.mixins import TenantMixin


class Appointment(TenantMixin, db.Model):
    __tablename__ = 'appointments'
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False, index=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)

    starts_at = db.Column(db.DateTime, nullable=False, index=True)
    ends_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='SCHEDULED', index=True)  # SCHEDULED|CONFIRMED|CANCELLED|NO_SHOW|DONE
    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    __table_args__ = (
        db.UniqueConstraint('patient_id', 'starts_at', name='uq_appointment_patient_time'),
        db.Index('idx_appt_doctor_time', 'doctor_id', 'starts_at'),
        db.Index('idx_appt_dept_status', 'department_id', 'status'),
        db.Index('idx_appt_patient_status', 'patient_id', 'status'),
    )

    patient = db.relationship('Patient', back_populates='appointments', lazy='selectin')
    doctor = db.relationship('User', back_populates='doctor_appointments', foreign_keys=[doctor_id], lazy='selectin')
    department = db.relationship('Department', back_populates='appointments', lazy='selectin')
    creator = db.relationship('User', foreign_keys=[created_by], lazy='selectin')
    workflows = db.relationship('PatientWorkflow', back_populates='appointment')


    def __repr__(self) -> str:
        return f"<Appointment patient={self.patient_id} at={self.starts_at}>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "doctor_id": self.doctor_id,
            "department_id": self.department_id,
            "starts_at": self.starts_at.isoformat() if self.starts_at else None,
            "ends_at": self.ends_at.isoformat() if self.ends_at else None,
            "status": self.status,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @db.validates('starts_at', 'ends_at')
    def validate_times(self, key, value):
        if value is not None and key == 'ends_at' and self.starts_at and value <= self.starts_at:
            raise ValueError("وقت النهاية يجب أن يكون بعد وقت البداية")
        return value
