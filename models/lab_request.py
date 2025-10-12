"""
المختبر - طلبات ونتائج (نسخة نهائية مبسطة)
"""
from datetime import datetime
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

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, index=True)

    visit = db.relationship('Visit', lazy='selectin')
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

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, index=True)

    request = db.relationship('LabRequest', back_populates='results', lazy='selectin')
    patient = db.relationship('Patient', back_populates='lab_results', lazy='selectin')
    performer = db.relationship('User', foreign_keys=[performed_by], lazy='select')

    def __repr__(self) -> str:
        return f"<LabResult {self.test_code} {self.value or ''}>"