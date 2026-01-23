"""
تقرير طبي مرتبط بزيارة - MedicalReport
"""
from datetime import datetime, timezone
from app_factory import db


class MedicalReport(db.Model):
    __tablename__ = 'medical_reports'
    
    id = db.Column(db.Integer, primary_key=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='CASCADE'), nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    body = db.Column(db.Text, nullable=True)
    signed_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    visit = db.relationship('Visit', lazy='selectin')
    signer = db.relationship('User', foreign_keys=[signed_by], lazy='select')

    def __repr__(self) -> str:
        return f"<MedicalReport {self.title}>"
