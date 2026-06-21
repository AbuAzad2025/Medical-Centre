"""
نموذج المريض - Patient (نسخة نهائية)
"""
from datetime import datetime, date, timezone
from sqlalchemy import Index
from sqlalchemy.orm import validates
from app_factory import db
from app.shared.mixins import TenantMixin


class Patient(TenantMixin, db.Model):
    __tablename__ = 'patients'
    __tenant_migration__ = True

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
        Index('idx_patient_name_birthdate', 'first_name', 'last_name', 'birth_date'),
        Index('idx_patient_insurance_created', 'insurance_company_id', 'created_at'),
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

    insurance_company = db.relationship('InsuranceCompany', foreign_keys=[insurance_company_id], lazy='selectin')

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

    prescriptions = db.relationship('Prescription', back_populates='patient',
        lazy='selectin', passive_deletes=True)
    medical_records = db.relationship('MedicalRecord', back_populates='patient', lazy='selectin')
    patient_satisfaction_surveys = db.relationship('PatientSatisfactionSurvey', back_populates='patient', lazy='selectin')

    ai_recommendations = db.relationship('AIRecommendation', back_populates='patient')
    patient_insights = db.relationship('PatientInsight', back_populates='patient')
    model_predictions = db.relationship('ModelPrediction', back_populates='patient')
    admissions = db.relationship('Admission', back_populates='patient')
    bed_transfers = db.relationship('BedTransfer', back_populates='patient')
    cds_alerts = db.relationship('CDSFiredAlert', back_populates='patient')
    care_plans = db.relationship('PatientCarePlan', back_populates='patient')
    dicom_studies = db.relationship('DICOMStudy', back_populates='patient')
    emar_administrations = db.relationship('eMARAdministration', back_populates='patient')
    emergency_cases = db.relationship('EmergencyCase', back_populates='patient')
    fhir_patient = db.relationship('FHIRPatient', back_populates='patient')
    coded_diagnoses = db.relationship('CodedDiagnosis', back_populates='patient')
    coded_procedures = db.relationship('CodedProcedure', back_populates='patient')
    pharmacy_sales = db.relationship('PharmacySale', back_populates='patient')
    medication_reconciliations = db.relationship('MedicationReconciliation', back_populates='patient')
    vital_signs = db.relationship('VitalSigns', back_populates='patient')
    online_bookings = db.relationship('OnlineBooking', back_populates='patient')
    surgeries = db.relationship('SurgerySchedule', back_populates='patient')
    allergies = db.relationship('PatientAllergy', back_populates='patient')
    disease_registries = db.relationship('DiseaseRegistry', back_populates='patient')
    problems = db.relationship('PatientProblem', back_populates='patient')
    allergy_intolerances = db.relationship('AllergyIntolerance', back_populates='patient')
    queue_items = db.relationship('QueueManagement', back_populates='patient')
    referrals = db.relationship('Referral', back_populates='patient')
    immunizations = db.relationship('Immunization', back_populates='patient')
    whatsapp_messages = db.relationship('WhatsAppMessage', back_populates='patient')
    workflows = db.relationship('PatientWorkflow', back_populates='patient')
    workflow_queue_items = db.relationship('WorkflowQueue', back_populates='patient')

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

    @validates('phone')
    def validate_phone(self, key, value):
        if value is not None:
            cleaned = ''.join(c for c in value if c.isdigit() or c in '+-() ')
            if len(cleaned) < 7:
                raise ValueError(f"رقم الهاتف قصير جداً: {value}")
            return cleaned
        return value

class PatientAllergy(TenantMixin, db.Model):
    __tablename__ = 'patient_allergies'
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False, index=True)
    allergen = db.Column(db.String(200), nullable=False, index=True)
    severity = db.Column(db.String(50), nullable=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    patient = db.relationship('Patient', back_populates='allergies')
