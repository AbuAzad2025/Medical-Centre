"""
عداد زيارات للمريض - Denormalized Counter (اختياري)
"""
from datetime import datetime
from app_factory import db


class PatientVisitCounter(db.Model):
    __tablename__ = 'patient_visit_counters'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False, index=True)
    visit_count = db.Column(db.Integer, default=0, nullable=False)
    last_visit_at = db.Column(db.DateTime, nullable=True)

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, index=True)

    def __repr__(self) -> str:
        return f"<PatientVisitCounter patient={self.patient_id} cnt={self.visit_count}>"