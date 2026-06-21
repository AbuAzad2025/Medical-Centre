"""
Two-Factor Authentication (2FA) / TOTP for Users
"""
from datetime import datetime, timezone
from app_factory import db
from app.shared.mixins import TenantMixin

class UserMFASettings(TenantMixin, db.Model):
    __tablename__ = 'user_mfa_settings'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True, index=True)

    # TOTP configuration
    totp_secret = db.Column(db.String(64), nullable=True)  # Encrypted base32 secret
    totp_enabled = db.Column(db.Boolean, default=False, nullable=False, index=True)
    totp_verified = db.Column(db.Boolean, default=False, nullable=False)
    backup_codes = db.Column(db.Text, nullable=True)  # JSON array of hashed backup codes
    backup_codes_used = db.Column(db.Text, nullable=True)  # JSON array of used codes

    # MFA session tracking
    last_mfa_at = db.Column(db.DateTime, nullable=True)
    mfa_method = db.Column(db.String(20), default='totp', nullable=False)  # totp | sms | email | app

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship('User', lazy='selectin')

    def __repr__(self):
        return f"<UserMFASettings user_id={self.user_id} enabled={self.totp_enabled}>"


class MFALoginAttempt(TenantMixin, db.Model):
    __tablename__ = 'mfa_login_attempts'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    success = db.Column(db.Boolean, default=False, nullable=False, index=True)
    method = db.Column(db.String(20), default='totp', nullable=False)
    failure_reason = db.Column(db.String(100), nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    user = db.relationship('User', lazy='selectin')

    def __repr__(self):
        return f"<MFALoginAttempt user_id={self.user_id} success={self.success}>"
