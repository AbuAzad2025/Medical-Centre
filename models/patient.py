"""
نموذج المريض - Patient (نسخة نهائية)
"""
from datetime import datetime, date, timezone
from sqlalchemy import Index
from app_factory import db


class Patient(db.Model):
    __tablename__ = 'patients'

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True, index=True)
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

    def get_gender_display(self):
        g = (self.gender or '').strip().upper()
        if not g:
            return 'غير محدد'
        if g in {'M', 'MALE', 'ذكر'}:
            return 'ذكر'
        if g in {'F', 'FEMALE', 'انثى', 'أنثى'}:
            return 'أنثى'
        return 'آخر'
    phone = db.Column(db.String(20), nullable=True, index=True)
    birth_date = db.Column(db.Date, nullable=True, index=True)
    gender = db.Column(db.String(10), nullable=True)  # M/F/Other
    address = db.Column(db.String(200), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    admin_notes = db.Column(db.Text, nullable=True)
    insurance_company_id = db.Column(db.Integer, db.ForeignKey('insurance_companies.id', ondelete='SET NULL'), nullable=True, index=True)
    insurance_member_number = db.Column(db.String(60), nullable=True)
    marital_status = db.Column(db.String(20), nullable=True)
    is_pregnant = db.Column(db.Boolean, default=False)
    pregnancy_weeks = db.Column(db.Integer, nullable=True)
    last_menstruation_date = db.Column(db.Date, nullable=True)
    pregnancy_notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    __table_args__ = (
        Index('idx_patient_name', 'first_name', 'last_name'),
    )

    visits = db.relationship(
        'Visit',
        back_populates='patient',
        cascade='all, delete-orphan',
        passive_deletes=True,
        lazy='select'
    )

    appointments = db.relationship(
        'Appointment',
        back_populates='patient',
        cascade='all, delete-orphan',
        passive_deletes=True,
        lazy='select'
    )

    insurance_company = db.relationship('InsuranceCompany', foreign_keys=[insurance_company_id], lazy='select')

    lab_results = db.relationship(
        'LabResult',
        back_populates='patient',
        lazy='select',
        passive_deletes=True
    )
    radiology_results = db.relationship(
        'RadiologyResult',
        back_populates='patient',
        lazy='select',
        passive_deletes=True
    )

    @property
    def visit_count(self):
        try:
            from models.patient_visit_counter import PatientVisitCounter
            pvc = PatientVisitCounter.query.filter_by(patient_id=self.id).first()
            if pvc:
                return int(pvc.visit_count or 0)
            from models.visit import Visit
            return Visit.query.filter_by(patient_id=self.id).count()
        except Exception:
            from models.visit import Visit
            return Visit.query.filter_by(patient_id=self.id).count()

    # الوصفات الطبية - سيتم تعريفها لاحقاً
    # prescriptions = db.relationship(
    #     'Prescription',
    #     back_populates='patient',
    #     lazy='selectin',
    #     passive_deletes=True
    # )

    def __repr__(self) -> str:
        return f"<Patient {self.first_name} {self.last_name}>"

    @property
    def age(self):
        try:
            if not self.birth_date:
                return None
            today = date.today()
            years = today.year - self.birth_date.year
            if (today.month, today.day) < (self.birth_date.month, self.birth_date.day):
                years -= 1
            return years
        except Exception:
            return None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "phone": self.phone,
            "gender": self.gender,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

class PatientAllergy(db.Model):
    __tablename__ = 'patient_allergies'
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False, index=True)
    allergen = db.Column(db.String(200), nullable=False, index=True)
    severity = db.Column(db.String(50), nullable=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    patient = db.relationship('Patient', backref='allergies')
