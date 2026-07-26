"""
Field Encryption Service — AES-256-GCM / Fernet field-level encryption at rest
Encrypts PHI/PII columns transparently with environment key management
"""
from sqlalchemy import select
import os
import base64
import logging
from typing import Optional, Union

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


class EncryptionConfigurationError(RuntimeError):
    """Raised when FIELD_ENCRYPTION_KEY is missing or invalid."""


class FieldEncryptionService:
    """
    Transparent field-level encryption for PHI/PII at rest.

    Uses Fernet (AES-128-CBC + HMAC-SHA256) by default for deterministic
    encryption of short strings. AES-256-GCM available for large payloads.

    Key management:
      - Primary key from FIELD_ENCRYPTION_KEY env var (32-byte base64 Fernet key)
      - Legacy plain-text rows detected by prefix check and left untouched
      - Batch migration helper provided for one-time encryption of existing data

    Usage:
        svc = FieldEncryptionService()
        encrypted = svc.encrypt("sensitive data")
        decrypted = svc.decrypt(encrypted)
    """

    LEGACY_PREFIX = b"$enc$"
    GCM_PREFIX = b"$gcm$"

    def __init__(self, key: Optional[str] = None):
        raw_key = (key or os.environ.get('FIELD_ENCRYPTION_KEY', '')).strip()
        if not raw_key:
            raise EncryptionConfigurationError(
                "FIELD_ENCRYPTION_KEY environment variable is required. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        try:
            self._fernet = Fernet(raw_key.encode('utf-8'))
        except Exception as exc:
            raise EncryptionConfigurationError(f"Invalid FIELD_ENCRYPTION_KEY: {exc}") from exc
        # Derive AES-256-GCM key from same material via PBKDF2 for large payloads
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=raw_key.encode('utf-8')[:16],
            iterations=480_000,
        )
        self._gcm_key = kdf.derive(raw_key.encode('utf-8'))

    def encrypt(self, plaintext: Union[str, bytes, None]) -> Optional[str]:
        """
        Encrypt plaintext. Returns base64-encoded ciphertext with prefix.
        None/empty input is returned as-is (allows nullable columns).
        """
        if plaintext is None or plaintext == '':
            return plaintext
        if isinstance(plaintext, str):
            data = plaintext.encode('utf-8')
        else:
            data = plaintext
        # Already encrypted? Return as-is to avoid double-encryption
        if data.startswith(self.LEGACY_PREFIX) or data.startswith(self.GCM_PREFIX):
            return data.decode('utf-8', errors='replace')
        try:
            token = self._fernet.encrypt(data)
            return (self.LEGACY_PREFIX + token).decode('utf-8')
        except Exception as exc:
            logger.error("Field encryption failed: %s", exc)
            raise

    def decrypt(self, ciphertext: Union[str, bytes, None]) -> Optional[str]:
        """
        Decrypt ciphertext. Returns plaintext string.
        Legacy plain-text rows (no prefix) are returned as-is.
        """
        if ciphertext is None or ciphertext == '':
            return ciphertext
        if isinstance(ciphertext, str):
            data = ciphertext.encode('utf-8')
        else:
            data = ciphertext
        # Legacy plain-text — return as-is (backward compatible)
        if not data.startswith(self.LEGACY_PREFIX) and not data.startswith(self.GCM_PREFIX):
            return ciphertext if isinstance(ciphertext, str) else ciphertext.decode('utf-8', errors='replace')
        try:
            if data.startswith(self.GCM_PREFIX):
                payload = base64.urlsafe_b64decode(data[len(self.GCM_PREFIX):])
                nonce = payload[:12]
                ct = payload[12:]
                aesgcm = AESGCM(self._gcm_key)
                pt = aesgcm.decrypt(nonce, ct, None)
                return pt.decode('utf-8')
            else:
                token = data[len(self.LEGACY_PREFIX):]
                pt = self._fernet.decrypt(token)
                return pt.decode('utf-8')
        except Exception as exc:
            logger.error("Field decryption failed: %s", exc)
            raise

    def encrypt_large(self, plaintext: Union[str, bytes, None]) -> Optional[str]:
        """AES-256-GCM for large payloads (>1KB or binary data)."""
        if plaintext is None or plaintext == '':
            return plaintext
        if isinstance(plaintext, str):
            data = plaintext.encode('utf-8')
        else:
            data = plaintext
        if data.startswith(self.LEGACY_PREFIX) or data.startswith(self.GCM_PREFIX):
            return data.decode('utf-8', errors='replace')
        try:
            aesgcm = AESGCM(self._gcm_key)
            nonce = os.urandom(12)
            ct = aesgcm.encrypt(nonce, data, None)
            payload = base64.urlsafe_b64encode(nonce + ct).decode('utf-8')
            return f"{self.GCM_PREFIX.decode('utf-8')}{payload}"
        except Exception as exc:
            logger.error("Large field encryption failed: %s", exc)
            raise

    def is_encrypted(self, value: Union[str, bytes, None]) -> bool:
        """Check if a value appears to be already encrypted."""
        if value is None:
            return False
        if isinstance(value, str):
            value = value.encode('utf-8')
        return value.startswith(self.LEGACY_PREFIX) or value.startswith(self.GCM_PREFIX)

    @classmethod
    def generate_key(cls) -> str:
        """Generate a new Fernet-compatible encryption key."""
        return Fernet.generate_key().decode('utf-8')

    @classmethod
    def migrate_column(cls, model_class, column_name: str, batch_size: int = 500, key: Optional[str] = None):
        """
        One-time batch encryption of an existing plaintext column.
        Must run inside an application context.

        Usage:
            with app.app_context():
                FieldEncryptionService.migrate_column(Patient, 'national_id')
        """
        svc = cls(key=key)
        from app.extensions import db
        session = db.session
        total = 0
        while True:
            rows = db.session.execute(select(model_class).filter(
                getattr(model_class, column_name).isnot(None)
            ).limit(batch_size)).scalars().all()
            if not rows:
                break
            for row in rows:
                val = getattr(row, column_name)
                if val and not svc.is_encrypted(val):
                    setattr(row, column_name, svc.encrypt(val))
                    total += 1
            session.commit()
            logger.info("Batch encrypted %s rows of %s.%s", len(rows), model_class.__name__, column_name)
        logger.info("Migration complete: %s total rows encrypted for %s.%s", total, model_class.__name__, column_name)
        return total
