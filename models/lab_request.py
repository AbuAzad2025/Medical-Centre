"""
المختبر - طلبات ونتائج (نسخة نهائية مبسطة)
"""
from datetime import datetime, timezone
from sqlalchemy import Index
from app_factory import db


class LabRequest(db.Model):
    __tablename__ = 'lab_requests'

    id = db.Column(db.Integer, primary_key=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='CASCADE'), nullable=False, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False, index=True)
    requested_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    request_number = db.Column(db.String(40), unique=True, nullable=True, index=True)
    status = db.Column(db.String(20), default='REQUESTED', index=True)  # REQUESTED|IN_PROGRESS|DONE|CANCELLED
    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    visit = db.relationship('Visit', back_populates='lab_requests', lazy='selectin')
    patient = db.relationship('Patient', lazy='selectin')
    requester = db.relationship('User', foreign_keys=[requested_by], lazy='select')

    results = db.relationship(
        'LabResult',
        back_populates='request',
        lazy='selectin',
        cascade='all, delete-orphan',
        passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<LabRequest #{self.request_number or self.id}>"
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "request_number": self.request_number,
            "visit_id": self.visit_id,
            "patient_id": self.patient_id,
            "requested_by": self.requested_by,
            "status": self.status,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class LabResult(db.Model):
    __tablename__ = 'lab_results'

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey('lab_requests.id', ondelete='CASCADE'), nullable=False, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False, index=True)
    performed_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    test_code = db.Column(db.String(50), nullable=False, index=True)
    test_name = db.Column(db.String(120), nullable=False)
    value = db.Column(db.String(120), nullable=True)
    unit = db.Column(db.String(40), nullable=True)
    reference_range = db.Column(db.String(120), nullable=True)
    status = db.Column(db.String(20), default='PENDING', index=True)  # PENDING|READY|VALIDATED
    notes = db.Column(db.Text, nullable=True)
    is_critical = db.Column(db.Boolean, default=False, nullable=False, index=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    request = db.relationship('LabRequest', back_populates='results', lazy='selectin')
    patient = db.relationship('Patient', back_populates='lab_results', lazy='selectin')
    performer = db.relationship('User', foreign_keys=[performed_by], lazy='select')

    def __repr__(self) -> str:
        return f"<LabResult {self.test_code} {self.value or ''}>"
