from datetime import datetime, timezone
from app_factory import db
from app.shared.mixins import TenantMixin


class PatientSatisfactionSurvey(TenantMixin, db.Model):
    __tablename__ = 'patient_satisfaction_surveys'

    id = db.Column(db.Integer, primary_key=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='CASCADE'), nullable=False, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='SET NULL'), nullable=True, index=True)
    token = db.Column(db.String(120), unique=True, nullable=False, index=True)
    rating = db.Column(db.Integer, nullable=True)
    comment = db.Column(db.Text, nullable=True)
    submitted_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    visit = db.relationship('Visit', back_populates='patient_satisfaction_surveys', lazy='selectin')
    patient = db.relationship('Patient', back_populates='patient_satisfaction_surveys', lazy='selectin')
