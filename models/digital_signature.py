"""
Digital Signature & Advanced Security
Electronic signatures for doctors, audit trails, password policy, encryption
"""
from datetime import datetime, timezone
from app_factory import db
from app.shared.mixins import TenantMixin

class DigitalSignature(TenantMixin, db.Model):
    """Electronic signature for clinical documents"""
    __tablename__ = 'digital_signatures'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    document_type = db.Column(db.String(100), nullable=False)  # PRESCRIPTION, REPORT, CONSENT, DISCHARGE
    document_id = db.Column(db.Integer, nullable=False)
    signature_hash = db.Column(db.String(500), nullable=False)
    signature_data = db.Column(db.Text, nullable=True)  # base64 image or SVG
    signing_method = db.Column(db.String(50), default='PASSWORD')  # PASSWORD, OTP, BIOMETRIC, SMARTCARD
    signed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)
    is_valid = db.Column(db.Boolean, default=True)
    revoked_at = db.Column(db.DateTime, nullable=True)
    revoked_reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', back_populates='digital_signatures')

    def __repr__(self):
        return f"<DigitalSignature {self.document_type}>"


class PasswordPolicy(TenantMixin, db.Model):
    """System-wide password policy configuration"""
    __tablename__ = 'password_policies'
    __tenant_migration__ = True
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    min_length = db.Column(db.Integer, default=8)
    require_uppercase = db.Column(db.Boolean, default=True)
    require_lowercase = db.Column(db.Boolean, default=True)
    require_digit = db.Column(db.Boolean, default=True)
    require_special = db.Column(db.Boolean, default=True)
    max_age_days = db.Column(db.Integer, default=90)
    history_count = db.Column(db.Integer, default=5)
    lockout_after_failures = db.Column(db.Integer, default=5)
    lockout_duration_minutes = db.Column(db.Integer, default=30)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class SessionLog(TenantMixin, db.Model):
    """Advanced session tracking for security"""
    __tablename__ = 'session_logs'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    session_id = db.Column(db.String(200), nullable=False)
    login_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    logout_at = db.Column(db.DateTime, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)
    device_type = db.Column(db.String(50), nullable=True)  # DESKTOP, MOBILE, TABLET
    browser = db.Column(db.String(100), nullable=True)
    os = db.Column(db.String(100), nullable=True)
    location = db.Column(db.String(200), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    terminated_by = db.Column(db.String(50), nullable=True)  # USER, ADMIN, TIMEOUT, SECURITY
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', back_populates='session_logs')

    def __repr__(self):
        return f"<SessionLog {self.session_id[:8]}>"


class EncryptedField(TenantMixin, db.Model):
    """Store encrypted sensitive data fields"""
    __tablename__ = 'encrypted_fields'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.String(100), nullable=False)  # Patient, User, etc.
    entity_id = db.Column(db.Integer, nullable=False)
    field_name = db.Column(db.String(100), nullable=False)
    encrypted_value = db.Column(db.Text, nullable=False)
    encryption_method = db.Column(db.String(50), default='AES-256-GCM')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
