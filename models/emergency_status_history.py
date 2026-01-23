from datetime import datetime, timezone
from app_factory import db


class EmergencyStatusHistory(db.Model):
    __tablename__ = 'emergency_status_history'

    id = db.Column(db.Integer, primary_key=True)
    emergency_id = db.Column(db.Integer, db.ForeignKey('emergency_cases.id', ondelete='CASCADE'), nullable=False, index=True)
    from_status = db.Column(db.String(50), nullable=True, index=True)
    to_status = db.Column(db.String(50), nullable=False, index=True)
    changed_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    emergency = db.relationship('EmergencyCase', lazy='select')
    actor = db.relationship('User', foreign_keys=[changed_by], lazy='select')

