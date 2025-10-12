"""
نموذج المريض - Patient (نسخة نهائية)
"""
from datetime import datetime, date
from sqlalchemy import Index
from app_factory import db


class Patient(db.Model):
    __tablename__ = 'patients'

    id = db.Column(db.Integer, primary_key=True)
    national_id = db.Column(db.String(32), unique=True, nullable=True, index=True)
    first_name = db.Column(db.String(80), nullable=False, index=True)
    last_name = db.Column(db.String(80), nullable=False, index=True)
    first_name_ar = db.Column(db.String(80), nullable=True)
    last_name_ar = db.Column(db.String(80), nullable=True)
    
    @property
    def full_name(self):
        """الاسم الكامل للمريض"""
        if self.first_name_ar and self.last_name_ar:
            return f"{self.first_name_ar} {self.last_name_ar}"
        return f"{self.first_name} {self.last_name}"
    phone = db.Column(db.String(20), nullable=True)
    birth_date = db.Column(db.Date, nullable=True)
    gender = db.Column(db.String(10), nullable=True)  # M/F/Other
    address = db.Column(db.String(200), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (
        Index('idx_patient_name', 'first_name', 'last_name'),
    )

    visits = db.relationship(
        'Visit',
        back_populates='patient',
        cascade='all, delete-orphan',
        passive_deletes=True,
        lazy='selectin'
    )

    appointments = db.relationship(
        'Appointment',
        back_populates='patient',
        cascade='all, delete-orphan',
        passive_deletes=True,
        lazy='selectin'
    )

    lab_results = db.relationship(
        'LabResult',
        back_populates='patient',
        lazy='selectin',
        passive_deletes=True
    )
    radiology_results = db.relationship(
        'RadiologyResult',
        back_populates='patient',
        lazy='selectin',
        passive_deletes=True
    )

    # الوصفات الطبية - سيتم تعريفها لاحقاً
    # prescriptions = db.relationship(
    #     'Prescription',
    #     back_populates='patient',
    #     lazy='selectin',
    #     passive_deletes=True
    # )

    def __repr__(self) -> str:
        return f"<Patient {self.first_name} {self.last_name}>"