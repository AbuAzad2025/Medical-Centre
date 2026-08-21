"""
API Key Model — machine-to-machine authentication for /api/* endpoints.
Keys are stored hashed (SHA-256); the plaintext prefix is kept for display.
"""

import hashlib
import secrets
from datetime import UTC, datetime

from app.shared.mixins import TenantMixin
from app_factory import db


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode('utf-8')).hexdigest()


class ApiKey(TenantMixin, db.Model):
    """مفتاح API للمؤسسات والتكاملات الخارجية"""

    __tablename__ = 'api_keys'
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)  # human label e.g. "Lab LIS integration"
    key_prefix = db.Column(db.String(12), nullable=False, index=True)  # first chars for display
    key_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)

    # Access control
    scopes = db.Column(db.String(500), nullable=False, default='read')  # comma-separated: read,write
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    created_by = db.Column(
        db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True
    )

    # Rate limiting per key (requests allowed per window)
    rate_limit_max = db.Column(db.Integer, default=100, nullable=False)
    rate_limit_window = db.Column(db.Integer, default=60, nullable=False)  # seconds

    # Lifecycle
    expires_at = db.Column(db.DateTime, nullable=True, index=True)
    last_used_at = db.Column(db.DateTime, nullable=True)
    revoked_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), nullable=False, index=True)

    __table_args__ = (
        db.Index('idx_api_key_tenant_active', 'tenant_id', 'is_active'),
        db.Index('idx_api_key_expires', 'expires_at'),
    )

    creator = db.relationship('User', foreign_keys=[created_by], lazy='selectin')

    @staticmethod
    def generate_raw_key() -> tuple[str, str, str]:
        """Generate a new raw API key.

        Returns (raw_key, prefix, hash). Only the raw key is shown once;
        store the prefix + hash in the database.
        """
        raw = f'mk_{secrets.token_urlsafe(32)}'
        return raw, raw[:10], _hash_key(raw)

    def verify(self, raw_key: str) -> bool:
        """Constant-time verification of a presented raw key."""
        return secrets.compare_digest(self.key_hash, _hash_key(raw_key))

    def is_valid(self) -> bool:
        """Check the key is active, not revoked, and not expired."""
        if not self.is_active or self.revoked_at is not None:
            return False
        if self.expires_at is not None:
            now = datetime.now(UTC)
            expires = (
                self.expires_at.replace(tzinfo=UTC) if self.expires_at.tzinfo is None else self.expires_at
            )
            if now > expires:
                return False
        return True

    def has_scope(self, scope: str) -> bool:
        granted = {s.strip().lower() for s in (self.scopes or '').split(',') if s.strip()}
        return scope.lower() in granted or '*' in granted

    def revoke(self) -> None:
        self.is_active = False
        self.revoked_at = datetime.now(UTC)

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'key_prefix': self.key_prefix,
            'scopes': [s.strip() for s in (self.scopes or '').split(',') if s.strip()],
            'is_active': self.is_active,
            'rate_limit': f'{self.rate_limit_max}/{self.rate_limit_window}s',
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'revoked_at': self.revoked_at.isoformat() if self.revoked_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f'<ApiKey {self.key_prefix}… ({self.name})>'
