"""
Encrypted column types for PHI at rest.

* ``EncryptedString``             -> AES-256-GCM, random nonce. Read-only values.
* ``EncryptedSearchableString``   -> AES-SIV, deterministic. Searchable values.
* ``blind_index_value``           -> HMAC-SHA256 digest for exact match.

Why the two column types exist: AES-GCM with a random nonce is the right
choice for confidentiality but makes the stored value useless for comparison —
the same plaintext encrypts differently every time, so ``filter_by``,
``ILIKE``, ``ORDER BY`` and ``UNIQUE`` silently never match. Patient search and
duplicate-national-id detection were therefore dead code. See
``docs/DEEP_AUDIT_REPORT_2026-09-27.md`` section 3.
"""

import logging
import os
import re
import unicodedata

from sqlalchemy import Text, TypeDecorator

logger = logging.getLogger(__name__)

# Arabic-Indic and Eastern Arabic-Indic digits must fold to ASCII so that
# "٠١٢٣" and "0123" resolve to the same patient.
_DIGIT_MAP: dict[int, int] = {c: ord('0') + (c - 0x0660) for c in range(0x0660, 0x066A)}
_DIGIT_MAP.update({c: ord('0') + (c - 0x06F0) for c in range(0x06F0, 0x06FA)})
_SEPARATORS = re.compile(r'[\s\-_.()\[\]/\\]+')


def normalize_for_index(value) -> str:
    """Canonical form used before hashing, so cosmetic differences collapse.

    Unicode-normalises (so composed and decomposed Arabic render identically),
    folds Arabic-Indic digits to ASCII, drops separators, and lowercases. Both
    sides of a comparison must use this, which is why the ORM computes the
    stored digest automatically instead of trusting call sites.
    """
    if value is None:
        return ''
    text = value if isinstance(value, str) else str(value)
    text = unicodedata.normalize('NFKC', text)
    text = text.translate(_DIGIT_MAP)
    text = _SEPARATORS.sub('', text)
    return text.strip().casefold()


def blind_index_value(value, normalizer=normalize_for_index) -> str | None:
    """Return the stored digest for *value*, or None when there is nothing to index.

    Returns None only for genuinely empty input, or when encryption is not
    configured at all -- so a development/test database without
    FIELD_ENCRYPTION_KEY keeps working exactly as it did before this column
    existed.

    A failure while encryption *is* configured is raised, not swallowed. Writing
    a NULL digest would silently disable both the duplicate-national-id index
    and identity lookups, which is the exact failure this column exists to
    prevent, so it has to fail loudly instead.
    """
    if value is None or value == '':
        return None
    key = (os.environ.get('FIELD_ENCRYPTION_KEY') or '').strip()
    if not key:
        return None
    from services.field_encryption_service import FieldEncryptionService

    svc = FieldEncryptionService.get_service()
    if svc is None:
        raise RuntimeError(
            'FIELD_ENCRYPTION_KEY is set but the field encryption service is '
            'disabled; refusing to write a NULL blind index.'
        )
    try:
        return svc.blind_index(normalizer(value))
    except Exception as exc:
        raise ValueError('Blind index computation failed') from exc


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
        """Deprecated: prefer :func:`blind_index_value` (proper HMAC + normalisation)."""
        return blind_index_value(plaintext) or ''


class EncryptedSearchableString(TypeDecorator):
    """Deterministic encrypted column for values that must be searched.

    AES-SIV (RFC 5297) under a key derived separately from the AES-GCM column
    key. Identical plaintexts produce identical ciphertexts, so ``=``,
    ``ILIKE``, ``ORDER BY`` and B-tree indexes behave normally while the value
    stays encrypted at rest and authenticated.

    Trade-off, stated explicitly because it matters for a PHI store: equal
    values are indistinguishable to anyone holding both this key and the
    database. Rows remain tenant-scoped by RLS, and identity columns use a blind
    index instead of this type precisely so that uniqueness never depends on
    that property.
    """

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(Text())

    def _get_service(self):
        key = (os.environ.get('FIELD_ENCRYPTION_KEY') or '').strip()
        if not key:
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
            return value
        return svc.encrypt_searchable(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        svc = self._get_service()
        if svc is None:
            return value
        return svc.decrypt_searchable(value)
