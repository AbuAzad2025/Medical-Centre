"""
السجل الطبي - MedicalRecord (ملاحظات عامة للمريض)
"""
from datetime import datetime
from app_factory import db


class MedicalRecord(db.Model):
    __tablename__ = 'medical_records'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    details = db.Column(db.Text, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, index=True)

    patient = db.relationship('Patient', lazy='selectin')
    creator = db.relationship('User', foreign_keys=[created_by], lazy='select')

    def __repr__(self) -> str:
        return f"<MedicalRecord {self.title}>"