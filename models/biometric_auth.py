"""
Biometric Authentication (WebAuthn / FIDO2)
"""
from datetime import datetime, timezone
from app_factory import db

class BiometricCredential(db.Model):
    __tablename__ = 'biometric_credentials'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)

    # WebAuthn credential fields
    credential_id = db.Column(db.String(255), nullable=False, unique=True, index=True)
    public_key = db.Column(db.Text, nullable=False)  # Base64 encoded COSE key
    sign_count = db.Column(db.Integer, default=0, nullable=False)

    # Device info
    device_name = db.Column(db.String(100), nullable=True)
    device_type = db.Column(db.String(30), nullable=True)  # fingerprint | face | pin | security_key
    aaguid = db.Column(db.String(64), nullable=True)
    user_verified = db.Column(db.Boolean, default=False, nullable=False)
    authenticator_attachment = db.Column(db.String(20), nullable=True)  # platform | cross-platform

    # Status
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    last_used_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship('User', lazy='selectin')

    def __repr__(self):
        return f"<BiometricCredential user={self.user_id} type={self.device_type}>"


class BiometricAuthChallenge(db.Model):
    __tablename__ = 'biometric_auth_challenges'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True)

    challenge = db.Column(db.String(255), nullable=False, unique=True, index=True)
    challenge_type = db.Column(db.String(20), nullable=False)  # registration | authentication

    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship('User', lazy='selectin')

    def __repr__(self):
        return f"<BiometricAuthChallenge type={self.challenge_type}>"
