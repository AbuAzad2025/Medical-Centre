"""
HL7 FHIR Resource Mapping
Basic FHIR R4 resources for interoperability
"""
from datetime import datetime, timezone
from app_factory import db

class FHIRPatient(db.Model):
    """FHIR Patient resource mapping"""
    __tablename__ = 'fhir_patients'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    internal_patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False, unique=True)
    fhir_id = db.Column(db.String(100), nullable=False, unique=True, index=True)  # UUID
    resource_json = db.Column(db.Text, nullable=False)  # Full FHIR JSON
    version = db.Column(db.Integer, default=1)
    last_synced = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = db.Column(db.Boolean, default=True)

    patient = db.relationship('Patient', backref='fhir_patient')


class FHIRObservation(db.Model):
    """FHIR Observation resource (vitals, lab results, etc.)"""
    __tablename__ = 'fhir_observations'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    fhir_id = db.Column(db.String(100), nullable=False, unique=True, index=True)
    internal_source_type = db.Column(db.String(50), nullable=False)  # LAB_RESULT, VITAL_SIGN, RADIOLOGY, etc.
    internal_source_id = db.Column(db.Integer, nullable=False)
    patient_fhir_id = db.Column(db.String(100), nullable=False, index=True)
    resource_json = db.Column(db.Text, nullable=False)
    observation_type = db.Column(db.String(100), nullable=True)  # LOINC code
    effective_datetime = db.Column(db.DateTime, nullable=True)
    issued_datetime = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    status = db.Column(db.String(20), default='FINAL')  # REGISTERED, PRELIMINARY, FINAL, AMENDED
    version = db.Column(db.Integer, default=1)
    is_active = db.Column(db.Boolean, default=True)


class FHIREncounter(db.Model):
    """FHIR Encounter resource (visits, admissions)"""
    __tablename__ = 'fhir_encounters'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    fhir_id = db.Column(db.String(100), nullable=False, unique=True, index=True)
    internal_source_type = db.Column(db.String(50), nullable=False)  # VISIT, ADMISSION, APPOINTMENT
    internal_source_id = db.Column(db.Integer, nullable=False)
    patient_fhir_id = db.Column(db.String(100), nullable=False, index=True)
    resource_json = db.Column(db.Text, nullable=False)
    encounter_type = db.Column(db.String(50), nullable=True)  # AMBULATORY, EMERGENCY, INPATIENT, VIRTUAL
    period_start = db.Column(db.DateTime, nullable=True)
    period_end = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='IN_PROGRESS')  # PLANNED, IN_PROGRESS, ONLEAVE, FINISHED, CANCELLED
    version = db.Column(db.Integer, default=1)
    is_active = db.Column(db.Boolean, default=True)


class FHIRDocumentReference(db.Model):
    """FHIR DocumentReference (DICOM, PDF reports, etc.)"""
    __tablename__ = 'fhir_document_references'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    fhir_id = db.Column(db.String(100), nullable=False, unique=True, index=True)
    internal_file_id = db.Column(db.Integer, db.ForeignKey('file_uploads.id'), nullable=True)
    patient_fhir_id = db.Column(db.String(100), nullable=False, index=True)
    resource_json = db.Column(db.Text, nullable=False)
    document_type = db.Column(db.String(100), nullable=True)  # LOINC code for document type
    status = db.Column(db.String(20), default='CURRENT')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class FHIRAuditLog(db.Model):
    """Audit log for FHIR API access"""
    __tablename__ = 'fhir_audit_logs'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(50), nullable=False)  # CREATE, READ, UPDATE, DELETE, SEARCH
    resource_type = db.Column(db.String(50), nullable=False)  # Patient, Observation, Encounter
    resource_id = db.Column(db.String(100), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    request_body = db.Column(db.Text, nullable=True)
    response_status = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
