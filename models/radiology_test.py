"""
الأشعة - نتيجة تصوير (Result)
"""
from datetime import datetime, timezone
from app_factory import db


class RadiologyResult(db.Model):
    __tablename__ = 'radiology_results'

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey('radiology_requests.id', ondelete='CASCADE'), nullable=False, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False, index=True)
    performed_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    study_uid = db.Column(db.String(64), nullable=True, index=True)
    pacs_url = db.Column(db.String(300), nullable=True)
    findings = db.Column(db.Text, nullable=True)
    impression = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='PENDING', index=True)  # PENDING|READY|VALIDATED
    notes = db.Column(db.Text, nullable=True)
    is_critical = db.Column(db.Boolean, default=False, nullable=False, index=True)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    reviewed_at = db.Column(db.DateTime, nullable=True, index=True)
    revised_after_review = db.Column(db.Boolean, default=False, nullable=False, index=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    request = db.relationship('RadiologyRequest', back_populates='results', lazy='selectin')
    patient = db.relationship('Patient', back_populates='radiology_results', lazy='selectin')
    performer = db.relationship('User', foreign_keys=[performed_by], lazy='select')
    reviewer = db.relationship('User', foreign_keys=[reviewed_by], lazy='select')

    def __repr__(self) -> str:
        return f"<RadiologyResult request={self.request_id}>"
