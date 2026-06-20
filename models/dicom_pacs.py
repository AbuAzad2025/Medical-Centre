"""
DICOM / PACS Integration
Medical imaging storage and retrieval
"""
from datetime import datetime, timezone
from app_factory import db
from app.shared.mixins import TenantMixin

class DICOMStudy(TenantMixin, db.Model):
    """DICOM study (exam session)"""
    __tablename__ = 'dicom_studies'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    study_instance_uid = db.Column(db.String(100), nullable=False, unique=True, index=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id', ondelete='RESTRICT'), nullable=False, index=True)
    radiology_request_id = db.Column(db.Integer, db.ForeignKey('radiology_requests.id', ondelete='SET NULL'), nullable=True, index=True)
    accession_number = db.Column(db.String(50), nullable=True, index=True)

    study_date = db.Column(db.Date, nullable=True)
    study_time = db.Column(db.Time, nullable=True)
    modality = db.Column(db.String(20), nullable=False)  # CT, MRI, XR, US, MG, etc.
    study_description = db.Column(db.String(500), nullable=True)
    body_part = db.Column(db.String(200), nullable=True)
    referring_physician = db.Column(db.String(200), nullable=True)

    # Status
    status = db.Column(db.String(50), default='RECEIVED')  # RECEIVED, PENDING_REVIEW, REVIEWED, REPORTED, ARCHIVED
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)

    # Storage
    storage_path = db.Column(db.String(500), nullable=True)
    file_size_mb = db.Column(db.Numeric(10, 2), nullable=True)
    series_count = db.Column(db.Integer, default=0)
    instance_count = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    patient = db.relationship('Patient', back_populates='dicom_studies')
    radiology_request = db.relationship('RadiologyRequest', back_populates='dicom_studies')
    reviewed_by = db.relationship('User', foreign_keys=[reviewed_by_id])
    series = db.relationship('DICOMSeries', back_populates='study', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<DICOMStudy {self.modality}>"


class DICOMSeries(TenantMixin, db.Model):
    """DICOM series within a study"""
    __tablename__ = 'dicom_series'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    study_id = db.Column(db.Integer, db.ForeignKey('dicom_studies.id', ondelete='CASCADE'), nullable=False, index=True)
    series_instance_uid = db.Column(db.String(100), nullable=False, unique=True, index=True)
    series_number = db.Column(db.Integer, nullable=True)
    modality = db.Column(db.String(20), nullable=False)
    series_description = db.Column(db.String(500), nullable=True)
    body_part = db.Column(db.String(200), nullable=True)
    instance_count = db.Column(db.Integer, default=0)
    storage_path = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    instances = db.relationship('DICOMInstance', back_populates='series', lazy='dynamic', cascade='all, delete-orphan')
    study = db.relationship('DICOMStudy', back_populates='series')


class DICOMInstance(TenantMixin, db.Model):
    """Individual DICOM image/instance"""
    __tablename__ = 'dicom_instances'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    series_id = db.Column(db.Integer, db.ForeignKey('dicom_series.id', ondelete='CASCADE'), nullable=False, index=True)
    sop_instance_uid = db.Column(db.String(100), nullable=False, unique=True, index=True)
    instance_number = db.Column(db.Integer, nullable=True)
    file_path = db.Column(db.String(500), nullable=True)
    thumbnail_path = db.Column(db.String(500), nullable=True)
    file_size_kb = db.Column(db.Integer, nullable=True)
    width = db.Column(db.Integer, nullable=True)
    height = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    series = db.relationship('DICOMSeries', back_populates='instances')


class PACSConfiguration(TenantMixin, db.Model):
    """PACS server configuration"""
    __tablename__ = 'pacs_configurations'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    pacs_type = db.Column(db.String(50), default='ORTHANC')  # ORTHANC, DCM4CHEE, CONQUEST
    server_host = db.Column(db.String(200), nullable=False)
    server_port = db.Column(db.Integer, default=8042)
    aet_title = db.Column(db.String(50), nullable=True)  # DICOM AET
    username = db.Column(db.String(100), nullable=True)
    password_encrypted = db.Column(db.String(500), nullable=True)
    base_url = db.Column(db.String(500), nullable=True)
    is_default = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
