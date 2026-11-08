"""Appointment waitlist — قائمة انتظار المواعيد.

Persists waitlist entries for walk-ins and overbooked slots. An entry moves
WAITING -> NOTIFIED -> CONVERTED (an appointment was booked) or CANCELLED.
A patient may hold at most one active (WAITING/NOTIFIED) entry per tenant for
the same doctor, which is enforced in the routes and audited.
"""

from datetime import UTC, datetime

from app.shared.mixins import TenantMixin
from app_factory import db

WAITLIST_ACTIVE_STATUSES = ('WAITING', 'NOTIFIED')
WAITLIST_STATUSES = ('WAITING', 'NOTIFIED', 'CONVERTED', 'CANCELLED')


class AppointmentWaitlist(TenantMixin, db.Model):
    __tablename__ = 'appointment_waitlist'
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(
        db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False, index=True
    )
    doctor_id = db.Column(
        db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True
    )
    department_id = db.Column(
        db.Integer, db.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True, index=True
    )
    created_by = db.Column(
        db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True
    )

    status = db.Column(db.String(20), default='WAITING', nullable=False, index=True)
    notes = db.Column(db.Text, nullable=True)
    preferred_time = db.Column(db.String(50), nullable=True)
    notified_at = db.Column(db.DateTime, nullable=True)
    converted_appointment_id = db.Column(
        db.Integer, db.ForeignKey('appointments.id', ondelete='SET NULL'), nullable=True
    )

    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(UTC), nullable=False, index=True
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        db.Index('idx_waitlist_tenant_status', 'tenant_id', 'status'),
        db.Index('idx_waitlist_patient_status', 'patient_id', 'status'),
    )

    patient = db.relationship('Patient', lazy='selectin')
    doctor = db.relationship(
        'User', foreign_keys=[doctor_id], lazy='selectin'
    )
    department = db.relationship('Department', lazy='selectin')

    def __repr__(self) -> str:
        return f'<AppointmentWaitlist patient={self.patient_id} status={self.status}>'

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'doctor_id': self.doctor_id,
            'department_id': self.department_id,
            'status': self.status,
            'notes': self.notes,
            'preferred_time': self.preferred_time,
            'notified_at': self.notified_at.isoformat() if self.notified_at else None,
            'converted_appointment_id': self.converted_appointment_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
