"""Telemedicine Consultation — M1: model linked to a visit + signed rooms."""

from datetime import UTC, datetime

from sqlalchemy import Index

from app.shared.mixins import TenantMixin
from app_factory import db


class Consultation(TenantMixin, db.Model):
    """Remote consultation tied to a visit.

    Lifecycle: SCHEDULED -> LIVE -> COMPLETED | CANCELLED | NO_SHOW
    Room access is granted via short-lived JWTs signed with SECRET_KEY.
    """

    __tablename__ = 'consultations'
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)
    visit_id = db.Column(
        db.Integer, db.ForeignKey('visits.id', ondelete='CASCADE'), nullable=False, index=True
    )
    doctor_id = db.Column(
        db.Integer, db.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False, index=True
    )
    patient_id = db.Column(
        db.Integer, db.ForeignKey('patients.id', ondelete='RESTRICT'), nullable=False, index=True
    )

    status = db.Column(db.String(20), default='SCHEDULED', nullable=False, index=True)
    scheduled_at = db.Column(db.DateTime, nullable=True)
    started_at = db.Column(db.DateTime, nullable=True)
    ended_at = db.Column(db.DateTime, nullable=True)

    notes = db.Column(db.Text, nullable=True)

    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        db.CheckConstraint(
            "status IN ('SCHEDULED','LIVE','COMPLETED','CANCELLED','NO_SHOW')",
            name='chk_consultation_status',
        ),
        Index('idx_consult_visit_status', 'visit_id', 'status'),
    )

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'visit_id': self.visit_id,
            'doctor_id': self.doctor_id,
            'patient_id': self.patient_id,
            'status': self.status,
            'scheduled_at': self.scheduled_at.isoformat() if self.scheduled_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'ended_at': self.ended_at.isoformat() if self.ended_at else None,
            'notes': self.notes,
        }
