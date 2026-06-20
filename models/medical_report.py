"""
تقرير طبي مرتبط بزيارة - MedicalReport
"""
from datetime import datetime, timezone
from sqlalchemy import Index
from app_factory import db
from app.shared.mixins import TenantMixin


class MedicalReport(TenantMixin, db.Model):
    __tablename__ = 'medical_reports'
    
    id = db.Column(db.Integer, primary_key=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='CASCADE'), nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    body = db.Column(db.Text, nullable=True)
    signed_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    __table_args__ = (
        Index('idx_med_report_visit_created', 'visit_id', 'created_at'),
        Index('idx_med_report_signer_created', 'signed_by', 'created_at'),
    )

    visit = db.relationship('Visit', back_populates='medical_reports', lazy='selectin')
    signer = db.relationship('User', foreign_keys=[signed_by], back_populates='signed_medical_reports', lazy='selectin')

    def __repr__(self) -> str:
        return f"<MedicalReport {self.title}>"
