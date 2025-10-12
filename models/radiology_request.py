"""
الأشعة - طلب تصوير (Request)
"""
from datetime import datetime
from app_factory import db


class RadiologyRequest(db.Model):
    __tablename__ = 'radiology_requests'

    id = db.Column(db.Integer, primary_key=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='CASCADE'), nullable=False, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False, index=True)
    requested_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    request_number = db.Column(db.String(40), unique=True, nullable=True, index=True)
    status = db.Column(db.String(20), default='REQUESTED', index=True)  # REQUESTED|IN_PROGRESS|DONE|CANCELLED
    modality = db.Column(db.String(20), nullable=True)  # XRay|CT|MRI|US
    body_part = db.Column(db.String(120), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, index=True)

    visit = db.relationship('Visit', lazy='selectin')
    patient = db.relationship('Patient', lazy='selectin')
    requester = db.relationship('User', foreign_keys=[requested_by], lazy='select')

    results = db.relationship(
        'RadiologyResult',
        back_populates='request',
        lazy='selectin',
        cascade='all, delete-orphan',
        passive_deletes=True
    )

    def __repr__(self) -> str:
        return f"<RadiologyRequest #{self.request_number or self.id}>"