"""
EncryptedString — SQLAlchemy TypeDecorator for transparent field-level encryption.
Wraps FieldEncryptionService so that reads decrypt and writes encrypt automatically.
"""
import os
import logging
from sqlalchemy import String, TypeDecorator

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
    impl = String
    cache_ok = True

    def __init__(self, max_length=None, *args, **kwargs):
        effective = (max_length or 255) + 80
        super().__init__(length=effective, *args, **kwargs)

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(String(length=self.length))

    def _get_service(self):
        if not os.environ.get('FIELD_ENCRYPTION_KEY'):
            return None
        try:
            from services.field_encryption_service import FieldEncryptionService
            return FieldEncryptionService()
        except Exception as e:
            return None

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        svc = self._get_service()
        if svc is None:
            return value
        return svc.encrypt(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        svc = self._get_service()
        if svc is None:
            return value
        return svc.decrypt(value)
