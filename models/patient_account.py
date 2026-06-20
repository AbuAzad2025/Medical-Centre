from datetime import datetime, timezone
from app_factory import db
from app.shared.mixins import TenantMixin


class PatientAccount(TenantMixin, db.Model):
    __tablename__ = 'patient_accounts'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False, unique=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    user = db.relationship('User', foreign_keys=[user_id], lazy='selectin')
    patient = db.relationship('Patient', foreign_keys=[patient_id], lazy='selectin')

