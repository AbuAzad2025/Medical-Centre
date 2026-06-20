"""
الأشعة - طلب تصوير (Request)
"""
from datetime import datetime, timezone
from sqlalchemy import Index
from app_factory import db


class RadiologyRequest(db.Model):
    __tablename__ = 'radiology_requests'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True, index=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='CASCADE'), nullable=False, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False, index=True)
    requested_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)

    request_number = db.Column(db.String(40), unique=True, nullable=True, index=True)
    status = db.Column(db.String(20), default='REQUESTED', index=True)  # REQUESTED|IN_PROGRESS|DONE|CANCELLED
    modality = db.Column(db.String(20), nullable=True)  # XRay|CT|MRI|US
    body_part = db.Column(db.String(120), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    __table_args__ = (
        Index('idx_rad_req_patient_created', 'patient_id', 'created_at'),
    )

    visit = db.relationship('Visit', back_populates='radiology_requests', lazy='selectin')
    patient = db.relationship('Patient', lazy='selectin')
    requester = db.relationship('User', foreign_keys=[requested_by], lazy='selectin')

    results = db.relationship(
        'RadiologyResult',
        back_populates='request',
        lazy='selectin',
        cascade='all, delete-orphan',
        passive_deletes=True
    )
    dicom_studies = db.relationship('DICOMStudy', back_populates='radiology_request')


    def __repr__(self) -> str:
        return f"<RadiologyRequest #{self.request_number or self.id}>"
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "request_number": self.request_number,
            "visit_id": self.visit_id,
            "patient_id": self.patient_id,
            "requested_by": self.requested_by,
            "status": self.status,
            "modality": self.modality,
            "body_part": self.body_part,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
