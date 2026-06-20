"""
ICD-10 / ICD-11 Coding System
Medical diagnosis and procedure coding per WHO / CMS standards
"""
from datetime import datetime, timezone
from app_factory import db
from app.shared.mixins import TenantMixin

class ICD10Code(db.Model):
    """ICD-10-CM diagnosis codes"""
    __tablename__ = 'icd10_codes'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), nullable=False, unique=True, index=True)
    category = db.Column(db.String(5), nullable=False, index=True)  # e.g., "A00", "E11"
    description = db.Column(db.Text, nullable=False)
    description_ar = db.Column(db.Text, nullable=True)
    is_billable = db.Column(db.Boolean, default=True)
    gender_restriction = db.Column(db.String(1), nullable=True)  # M, F, or null
    age_min = db.Column(db.Integer, nullable=True)
    age_max = db.Column(db.Integer, nullable=True)
    chapter = db.Column(db.String(200), nullable=True)
    chapter_code = db.Column(db.String(5), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    diagnoses = db.relationship('CodedDiagnosis', back_populates='icd_code', lazy='dynamic')

    def __repr__(self):
        return f"<ICD10Code {self.code}>"


class CPTCode(db.Model):
    """Current Procedural Terminology codes"""
    __tablename__ = 'cpt_codes'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), nullable=False, unique=True, index=True)
    description = db.Column(db.Text, nullable=False)
    description_ar = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(100), nullable=True)  # Surgery, Radiology, Lab, etc.
    subcategory = db.Column(db.String(100), nullable=True)
    is_billable = db.Column(db.Boolean, default=True)
    typical_fee = db.Column(db.Numeric(12, 2), nullable=True)
    rvu_work = db.Column(db.Numeric(6, 2), nullable=True)
    rvu_pe = db.Column(db.Numeric(6, 2), nullable=True)  # Practice expense
    rvu_mp = db.Column(db.Numeric(6, 2), nullable=True)  # Malpractice
    modifier_allowed = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    procedures = db.relationship('CodedProcedure', back_populates='cpt_code', lazy='dynamic')

    def __repr__(self):
        return f"<CPTCode {self.code}>"


class DRGCode(db.Model):
    """Diagnosis-Related Group codes for inpatient billing"""
    __tablename__ = 'drg_codes'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), nullable=False, unique=True, index=True)
    description = db.Column(db.Text, nullable=False)
    mdc = db.Column(db.String(5), nullable=True)  # Major Diagnostic Category
    weight = db.Column(db.Numeric(6, 4), nullable=True)
    geometric_mean_los = db.Column(db.Numeric(6, 2), nullable=True)  # Length of stay
    arithmetic_mean_los = db.Column(db.Numeric(6, 2), nullable=True)
    is_medical = db.Column(db.Boolean, default=True)  # vs surgical
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    admissions = db.relationship('Admission', back_populates='drg')


    def __repr__(self):
        return f"<DRGCode {self.code}>"


class CodedDiagnosis(TenantMixin, db.Model):
    """Link patient encounters to ICD-10 codes"""
    __tablename__ = 'coded_diagnoses'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='RESTRICT'), nullable=False, index=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='SET NULL'), nullable=True, index=True)
    medical_record_id = db.Column(db.Integer, db.ForeignKey('medical_records.id', ondelete='SET NULL'), nullable=True, index=True)
    icd10_code_id = db.Column(db.Integer, db.ForeignKey('icd10_codes.id', ondelete='RESTRICT'), nullable=False, index=True)
    diagnosis_type = db.Column(db.String(20), default='PRIMARY')  # PRIMARY, SECONDARY, ADMITTING, DISCHARGE
    onset_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), default='ACTIVE')  # ACTIVE, RESOLVED, CHRONIC, RELAPSE
    notes = db.Column(db.Text, nullable=True)
    coded_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    coded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    patient = db.relationship('Patient', back_populates='coded_diagnoses')
    visit = db.relationship('Visit', back_populates='coded_diagnoses')
    medical_record = db.relationship('MedicalRecord', back_populates='coded_diagnoses')
    coded_by = db.relationship('User', foreign_keys=[coded_by_id])
    icd_code = db.relationship('ICD10Code', back_populates='diagnoses')


    def __repr__(self):
        return f"<CodedDiagnosis {self.diagnosis_type}>"


class CodedProcedure(TenantMixin, db.Model):
    """Link patient encounters to CPT/HCPCS codes"""
    __tablename__ = 'coded_procedures'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='RESTRICT'), nullable=False, index=True)
    visit_id = db.Column(db.Integer, db.ForeignKey('visits.id', ondelete='SET NULL'), nullable=True, index=True)
    cpt_code_id = db.Column(db.Integer, db.ForeignKey('cpt_codes.id', ondelete='RESTRICT'), nullable=False, index=True)
    quantity = db.Column(db.Integer, default=1)
    modifier = db.Column(db.String(10), nullable=True)
    performed_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), default='PLANNED')  # PLANNED, PERFORMED, CANCELLED
    notes = db.Column(db.Text, nullable=True)
    billed = db.Column(db.Boolean, default=False)
    coded_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    patient = db.relationship('Patient', back_populates='coded_procedures')
    visit = db.relationship('Visit', back_populates='coded_procedures')
    coded_by = db.relationship('User', foreign_keys=[coded_by_id])
    cpt_code = db.relationship('CPTCode', back_populates='procedures')


    def __repr__(self):
        return f"<CodedProcedure {self.quantity}x>"
