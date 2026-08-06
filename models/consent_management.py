"""
Consent Management — patient consent tracking for GDPR/HIPAA compliance
Tracks consent for treatment, data processing, telemedicine, research, and marketing
"""

from datetime import UTC, datetime

from app.shared.encrypted_type import EncryptedString
from app.shared.mixins import TenantMixin
from app_factory import db


class PatientConsent(TenantMixin, db.Model):
    """
    Versioned patient consent records.
    Every consent change creates a new version — previous versions are immutable.
    """

    __tablename__ = 'patient_consents'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(
        db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False, index=True
    )

    # Consent type categorization
    consent_type = db.Column(db.String(50), nullable=False, index=True)
    # treatment, data_processing, telemedicine, research, marketing, photo_video, third_party_share

    # Consent scope / description
    scope_description = db.Column(db.Text, nullable=False)
    # e.g., "I consent to the processing of my personal health data for treatment purposes"

    # Status
    status = db.Column(db.String(20), nullable=False, default='granted', index=True)
    # granted, withdrawn, expired, pending_review

    # Versioning
    version = db.Column(db.Integer, nullable=False, default=1)
    previous_version_id = db.Column(db.Integer, db.ForeignKey('patient_consents.id'), nullable=True)

    # Effective dates
    granted_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=True)
    withdrawn_at = db.Column(db.DateTime, nullable=True)
    withdrawal_reason = db.Column(db.Text, nullable=True)

    # Grant context
    granted_by_patient = db.Column(db.Boolean, default=True, nullable=False)
    # False if granted by legal guardian / representative
    guardian_name = db.Column(EncryptedString(120), nullable=True)
    guardian_relationship = db.Column(db.String(50), nullable=True)
    guardian_id_number = db.Column(EncryptedString(50), nullable=True)

    # How consent was captured
    capture_method = db.Column(db.String(50), nullable=False, default='written')
    # written, digital_signature, verbal, video, biometric
    capture_document_id = db.Column(db.Integer, db.ForeignKey('file_uploads.id'), nullable=True)
    # Link to scanned consent form or digital signature record

    # Who recorded the consent
    recorded_by_user_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=False, index=True
    )

    # Tenant + audit
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        db.UniqueConstraint(
            'patient_id', 'consent_type', 'version', name='uq_patient_consent_version'
        ),
        db.Index('idx_consent_status_type', 'status', 'consent_type'),
        db.Index('idx_consent_patient_active', 'patient_id', 'status'),
    )

    patient = db.relationship('Patient', backref='consents', lazy='selectin')
    recorded_by = db.relationship('User', foreign_keys=[recorded_by_user_id], lazy='selectin')
    previous_version = db.relationship('PatientConsent', remote_side=[id], lazy='selectin')
    capture_document = db.relationship(
        'FileUpload', foreign_keys=[capture_document_id], lazy='selectin'
    )

    def is_active(self) -> bool:
        """Check if consent is currently valid."""
        if self.status != 'granted':
            return False
        return not (self.expires_at and datetime.now(UTC) > self.expires_at)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'consent_type': self.consent_type,
            'scope_description': self.scope_description,
            'status': self.status,
            'version': self.version,
            'granted_at': self.granted_at.isoformat() if self.granted_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'withdrawn_at': self.withdrawn_at.isoformat() if self.withdrawn_at else None,
            'capture_method': self.capture_method,
            'is_active': self.is_active(),
        }


class ConsentTemplate(TenantMixin, db.Model):
    """Pre-defined consent forms/templates for different procedures and data uses."""

    __tablename__ = 'consent_templates'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    consent_type = db.Column(db.String(50), nullable=False, index=True)
    scope_description = db.Column(db.Text, nullable=False)
    default_expiry_days = db.Column(db.Integer, nullable=True)  # None = no expiry
    requires_guardian = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class ConsentAuditLog(TenantMixin, db.Model):
    """Immutable audit trail of every consent-related action."""

    __tablename__ = 'consent_audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    consent_id = db.Column(
        db.Integer,
        db.ForeignKey('patient_consents.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    action = db.Column(db.String(50), nullable=False, index=True)
    # granted, withdrawn, expired, viewed, exported
    performed_by_user_id = db.Column(
        db.Integer, db.ForeignKey('users.id'), nullable=True, index=True
    )
    patient_id = db.Column(
        db.Integer, db.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False, index=True
    )
    details = db.Column(db.Text, nullable=True)  # JSON
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), nullable=False)

    __table_args__ = (db.Index('idx_consent_audit_patient', 'patient_id', 'created_at'),)
