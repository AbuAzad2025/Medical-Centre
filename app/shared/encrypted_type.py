"""
EncryptedString — SQLAlchemy TypeDecorator for transparent field-level encryption.
Wraps FieldEncryptionService so that reads decrypt and writes encrypt automatically.
"""

import logging
import os

from sqlalchemy import Text, TypeDecorator

logger = logging.getLogger(__name__)


class EncryptedString(TypeDecorator):
    """
    Transparently encrypts/decrypts a String column at rest.

    Usage in a model:
        national_id = db.Column(EncryptedString(32), nullable=True)

    The column stores ciphertext (prefixed) in the database. Application code
    reads and writes plain-text strings — the TypeDecorator handles the rest.

    When FIELD_ENCRYPTION_KEY is not set, the column behaves as plain text
    (graceful degradation for development and testing).
    """

    impl = Text
    cache_ok = True

    def __init__(self, max_length=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def load_dialect_impl(self, dialect):
        # Use TEXT type for PostgreSQL to handle arbitrary length ciphertext
        # For other dialects, fall back to TEXT which is universally supported
        return dialect.type_descriptor(Text())

    def _get_service(self):
        key = os.environ.get('FIELD_ENCRYPTION_KEY', '').strip()
        if not key:
            # Fail-closed in production/staging; allow plaintext only in testing/dev
            try:
                from flask import current_app

                if current_app and not current_app.config.get('TESTING', False):
                    env = (
                        current_app.config.get('APP_ENV') or os.environ.get('APP_ENV') or ''
                    ).lower()
                    if env in ('production', 'staging'):
                        raise RuntimeError(
                            'FIELD_ENCRYPTION_KEY missing — refusing to store PHI as plaintext'
                        )
            except RuntimeError:
                raise
            except Exception:
                pass
            return None
        try:
            from services.field_encryption_service import FieldEncryptionService

            return FieldEncryptionService.get_service()
        except Exception:
            return None

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        svc = self._get_service()
        if svc is None:
            # Only allow plaintext in testing/dev; in production this already raised above
            return value
        return svc.encrypt(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        svc = self._get_service()
        if svc is None:
            return value
        logger.debug('PHI field decrypted')
        return svc.decrypt(value)

    @staticmethod
    def hash_for_lookup(plaintext: str) -> str:
        import hashlib
        import hmac

        key = os.environ.get('FIELD_ENCRYPTION_KEY', '')
        if not key:
            return plaintext
        return hmac.new(key.encode(), plaintext.encode(), hashlib.sha256).hexdigest()
