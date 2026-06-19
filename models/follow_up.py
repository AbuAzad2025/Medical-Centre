from datetime import datetime, timezone
from sqlalchemy import Index, CheckConstraint
from app_factory import db


class FollowUpRequest(db.Model):
    __tablename__ = 'follow_up_requests'

    id = db.Column(db.Integer, primary_key=True)

    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False, index=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    source_visit_id = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='SET NULL'), nullable=True, index=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.id', ondelete='SET NULL'), nullable=True, index=True)

    suggested_date = db.Column(db.Date, nullable=False, index=True)
    notes = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(16), nullable=False, default='PENDING', index=True)

    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        CheckConstraint("status IN ('PENDING','SCHEDULED','DONE','CANCELLED')", name='chk_follow_up_requests_status'),
        Index('idx_follow_up_requests_patient_status_date', 'patient_id', 'status', 'suggested_date'),
        Index('idx_follow_up_requests_doctor_status_date', 'doctor_id', 'status', 'suggested_date'),
    )

    patient = db.relationship('Patient', lazy='selectin')
    doctor = db.relationship('User', foreign_keys=[doctor_id], lazy='selectin')
    source_visit = db.relationship('Visit', foreign_keys=[source_visit_id], lazy='selectin')
    appointment = db.relationship('Appointment', foreign_keys=[appointment_id], lazy='selectin')
    creator = db.relationship('User', foreign_keys=[created_by], lazy='selectin')

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'doctor_id': self.doctor_id,
            'source_visit_id': self.source_visit_id,
            'appointment_id': self.appointment_id,
            'suggested_date': self.suggested_date.isoformat() if self.suggested_date else None,
            'notes': self.notes,
            'status': self.status,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

