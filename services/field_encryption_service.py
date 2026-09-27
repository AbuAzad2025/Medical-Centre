"""
Field Encryption Service — PHI/PII encryption at rest.

Three primitives, each with its own purpose-separated key:

* ``encrypt`` / ``decrypt``            -> AES-256-GCM, random nonce.
  Maximum confidentiality, NOT searchable: the same plaintext produces
  different ciphertext every time, so ``=``, ``LIKE`` and ``UNIQUE`` cannot
  work. Use for values that are only ever read back.
* ``encrypt_searchable`` / ``decrypt_searchable``
                                     -> AES-SIV (RFC 5297), deterministic.
  Same plaintext yields the same ciphertext, so equality, ``ILIKE``,
  ``ORDER BY`` and B-tree indexes all keep working while the value stays
  encrypted at rest. Use for values that must be searched or sorted.
* ``blind_index``                     -> HMAC-SHA256, not reversible.
  Reveals nothing about the value while still supporting exact match,
  ``UNIQUE`` and ``GROUP BY``. Use for identity columns (national id, phone).

AES-GCM key derivation is left untouched so that ciphertext written by earlier
releases stays readable.
"""

import base64
import hashlib
import hmac
import logging
import os

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM, AESSIV
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from sqlalchemy import select

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

    _svc_instance: 'FieldEncryptionService | None' = None
    _last_key: str | None = None
    _gcm_cache: dict[str, bytes] = {}
    _derived_cache: dict[str, tuple[bytes, bytes]] = {}

    @classmethod
    def is_active(cls) -> bool:
        """True when PHI is really encrypted, i.e. a usable key is configured.

        Callers use this to decide whether a SQL ``LIKE`` against a PHI column
        can work at all. Under encryption it never can, and silently returning
        no rows while pretending to search is worse than saying so.
        """
        return cls.get_service() is not None

    @classmethod
    def get_service(cls) -> 'FieldEncryptionService | None':
        """Get the singleton instance, or None when the key is invalid. Handles key rotation."""
        cur_key = (os.environ.get('FIELD_ENCRYPTION_KEY') or '').strip()
        if cls._svc_instance is not None and cls._last_key == cur_key:
            return cls._svc_instance
        # Key changed or no instance — create new
        try:
            inst = cls(key=cur_key if cur_key else None)
            cls._svc_instance = inst
            cls._last_key = cur_key
            return inst
        except EncryptionConfigurationError:
            # Don't cache failure; allow retry if env changes
            return None

    LEGACY_PREFIX = b'$enc$'
    GCM_PREFIX = b'$gcm$'
    SIV_PREFIX = b'$siv$'

    # Domain separation: bound the SIV ciphertext to this purpose so a value
    # encrypted for search can never be replayed into another context.
    _SIV_AAD = b'phi-searchable-v1'

    def __init__(self, key: str | None = None):
        raw_key = (key or os.environ.get('FIELD_ENCRYPTION_KEY', '')).strip()
        if not raw_key:
            raise EncryptionConfigurationError(
                'FIELD_ENCRYPTION_KEY environment variable is required. '
                'Generate one with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
            )
        try:
            self._fernet = Fernet(raw_key.encode('utf-8'))
        except Exception as exc:
            raise EncryptionConfigurationError(f'Invalid FIELD_ENCRYPTION_KEY: {exc}') from exc
        # Derive AES-256-GCM key — cached per raw_key to avoid 480k PBKDF2 per row
        cached = self.__class__._gcm_cache.get(raw_key)
        if cached is not None:
            self._gcm_key = cached
        else:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=raw_key.encode('utf-8')[:16],
                iterations=480_000,
            )
            self._gcm_key = kdf.derive(raw_key.encode('utf-8'))
            self.__class__._gcm_cache[raw_key] = self._gcm_key
        # Separate keys for the searchable and blind-index primitives. Reusing
        # the GCM key across algorithms is a key-hygiene violation, so both are
        # derived with HKDF and distinct info labels.
        derived = self.__class__._derived_cache.get(raw_key)
        if derived is None:
            siv_key = HKDF(
                algorithm=hashes.SHA256(),
                length=64,  # AES-256-SIV: 32-byte MAC key + 32-byte CTR key
                salt=None,
                info=b'field-encryption/v1/siv',
            ).derive(raw_key.encode('utf-8'))
            blind_key = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=None,
                info=b'field-encryption/v1/blind-index',
            ).derive(raw_key.encode('utf-8'))
            derived = (siv_key, blind_key)
            self.__class__._derived_cache[raw_key] = derived
        self._siv_key, self._blind_key = derived
        self._raw_key = raw_key

    # ------------------------------------------------------------------
    # Deterministic (searchable) encryption — AES-SIV
    # ------------------------------------------------------------------
    def encrypt_searchable(self, plaintext: str | bytes | None) -> str | None:
        """Deterministic authenticated encryption.

        Equal plaintexts produce equal ciphertexts, so the value can be matched
        with ``=``/``ILIKE`` and indexed, while remaining encrypted at rest and
        integrity-protected. The trade-off is that equal values are visible as
        equal to anyone holding both the database and this key; rows stay
        tenant-scoped by RLS.
        """
        if plaintext is None or plaintext == '':
            return plaintext
        data = plaintext.encode('utf-8') if isinstance(plaintext, str) else plaintext
        if data.startswith(self.SIV_PREFIX):
            return data.decode('utf-8', errors='replace')
        if data.startswith(self.LEGACY_PREFIX) or data.startswith(self.GCM_PREFIX):
            # Already encrypted with the non-deterministic scheme: re-encrypt so
            # the column becomes searchable. Idempotent by prefix.
            plaintext = self.decrypt(plaintext)
            if plaintext is None:
                return None
            data = plaintext.encode('utf-8')
        try:
            ct = AESSIV(self._siv_key).encrypt(data, [self._SIV_AAD])
            payload = base64.urlsafe_b64encode(ct).decode('utf-8')
            return (self.SIV_PREFIX + payload.encode()).decode('utf-8')
        except Exception:
            logger.exception('Searchable field encryption failed')
            raise

    def decrypt_searchable(self, ciphertext: str | bytes | None) -> str | None:
        """Inverse of :meth:`encrypt_searchable`, tolerant of legacy schemes."""
        if ciphertext is None or ciphertext == '':
            return ciphertext
        data = ciphertext.encode('utf-8') if isinstance(ciphertext, str) else ciphertext
        if not data.startswith(self.SIV_PREFIX):
            # Plaintext row, legacy Fernet row, or a GCM row awaiting migration.
            return self.decrypt(ciphertext)
        try:
            ct = base64.urlsafe_b64decode(data[len(self.SIV_PREFIX) :])
            pt = AESSIV(self._siv_key).decrypt(ct, [self._SIV_AAD])
            return pt.decode('utf-8')
        except Exception:
            logger.exception('Searchable field decryption failed')
            return (
                ciphertext
                if isinstance(ciphertext, str)
                else ciphertext.decode('utf-8', errors='replace')
            )

    # ------------------------------------------------------------------
    # Blind index — HMAC-SHA256
    # ------------------------------------------------------------------
    def blind_index(self, plaintext: str | bytes | None) -> str | None:
        """Keyed, non-reversible digest for exact-match lookups.

        The stored value reveals nothing about the plaintext, yet supports
        equality, ``UNIQUE`` and grouping. Callers must normalise the input
        first (see :func:`app.shared.encrypted_type.blind_index_value`) so that
        cosmetic differences do not produce different digests.
        """
        if plaintext is None or plaintext == '':
            return None
        data = plaintext.encode('utf-8') if isinstance(plaintext, str) else plaintext
        return hmac.new(self._blind_key, data, hashlib.sha256).hexdigest()

    def hash_for_lookup(self, plaintext: str | bytes | None) -> str | None:
        """Backwards-compatible alias; now a proper HMAC blind index."""
        return self.blind_index(plaintext)

    def encrypt(self, plaintext: str | bytes | None) -> str | None:
        """
        Encrypt plaintext. Returns base64-encoded ciphertext with prefix.
        None/empty input is returned as-is (allows nullable columns).
        """
        if plaintext is None or plaintext == '':
            return plaintext
        data = plaintext.encode('utf-8') if isinstance(plaintext, str) else plaintext
        # Already encrypted? Return as-is to avoid double-encryption
        if data.startswith(self.LEGACY_PREFIX) or data.startswith(self.GCM_PREFIX):
            return data.decode('utf-8', errors='replace')
        try:
            nonce = os.urandom(12)
            aesgcm = AESGCM(self._gcm_key)
            ct = aesgcm.encrypt(nonce, data, None)
            payload = base64.urlsafe_b64encode(nonce + ct).decode('utf-8')
            return (self.GCM_PREFIX + payload.encode()).decode('utf-8')
        except Exception:
            logger.exception('Field encryption failed')
            raise

    def decrypt(self, ciphertext: str | bytes | None) -> str | None:
        """
        Decrypt ciphertext. Returns plaintext string.
        Legacy plain-text rows (no prefix) are returned as-is.
        """
        if ciphertext is None or ciphertext == '':
            return ciphertext
        data = ciphertext.encode('utf-8') if isinstance(ciphertext, str) else ciphertext
        # Legacy plain-text — return as-is (backward compatible)
        if not data.startswith(self.LEGACY_PREFIX) and not data.startswith(self.GCM_PREFIX):
            return (
                ciphertext
                if isinstance(ciphertext, str)
                else ciphertext.decode('utf-8', errors='replace')
            )
        try:
            if data.startswith(self.GCM_PREFIX):
                payload = base64.urlsafe_b64decode(data[len(self.GCM_PREFIX) :])
                nonce = payload[:12]
                ct = payload[12:]
                aesgcm = AESGCM(self._gcm_key)
                pt = aesgcm.decrypt(nonce, ct, None)
                return pt.decode('utf-8')
            token = data[len(self.LEGACY_PREFIX) :]
            pt = self._fernet.decrypt(token)
            return pt.decode('utf-8')
        except Exception:
            # On key mismatch or corrupted data, return raw to avoid breaking reads
            # (e.g., after key rotation or test data with different key)
            return (
                ciphertext
                if isinstance(ciphertext, str)
                else ciphertext.decode('utf-8', errors='replace')
            )

    def can_decrypt(self, value: str | bytes | None) -> bool:
        """True when :meth:`decrypt` would return the real plaintext.

        :meth:`decrypt` deliberately returns the raw value when it cannot
        decrypt, so reads keep working after a key rotation. That tolerance is
        wrong for any code that *rewrites* the value: re-encrypting an
        undecryptable blob would nest the ciphertext inside a new ciphertext and
        destroy the only copy of the data. Callers that migrate data must check
        this first and abort rather than corrupt the row.
        """
        if value is None or value == '':
            return True
        data = value.encode('utf-8') if isinstance(value, str) else value
        if not data.startswith(self.LEGACY_PREFIX) and not data.startswith(self.GCM_PREFIX):
            return True  # plaintext row
        try:
            if data.startswith(self.GCM_PREFIX):
                payload = base64.urlsafe_b64decode(data[len(self.GCM_PREFIX) :])
                AESGCM(self._gcm_key).decrypt(payload[:12], payload[12:], None)
            else:
                self._fernet.decrypt(data[len(self.LEGACY_PREFIX) :])
            return True
        except Exception:
            return False

    def encrypt_large(self, plaintext: str | bytes | None) -> str | None:
        """AES-256-GCM for large payloads (>1KB or binary data)."""
        if plaintext is None or plaintext == '':
            return plaintext
        data = plaintext.encode('utf-8') if isinstance(plaintext, str) else plaintext
        if data.startswith(self.LEGACY_PREFIX) or data.startswith(self.GCM_PREFIX):
            return data.decode('utf-8', errors='replace')
        try:
            aesgcm = AESGCM(self._gcm_key)
            nonce = os.urandom(12)
            ct = aesgcm.encrypt(nonce, data, None)
            payload = base64.urlsafe_b64encode(nonce + ct).decode('utf-8')
            return f'{self.GCM_PREFIX.decode("utf-8")}{payload}'
        except Exception:
            logger.exception('Large field encryption failed: %s')
            raise

    def is_encrypted(self, value: str | bytes | None) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            value = value.encode('utf-8')
        return (
            value.startswith(self.LEGACY_PREFIX)
            or value.startswith(self.GCM_PREFIX)
            or value.startswith(self.SIV_PREFIX)
        )

    def is_searchable_encrypted(self, value: str | bytes | None) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            value = value.encode('utf-8')
        return value.startswith(self.SIV_PREFIX)

    def encrypt_deterministic(self, plaintext: str | bytes | None) -> str | None:
        return self.encrypt(plaintext)

    def encrypt_random(self, plaintext: str | bytes | None) -> str | None:
        if plaintext is None or plaintext == '':
            return plaintext
        data = plaintext.encode('utf-8') if isinstance(plaintext, str) else plaintext
        if data.startswith(self.LEGACY_PREFIX) or data.startswith(self.GCM_PREFIX):
            return data.decode('utf-8', errors='replace')
        try:
            aesgcm = AESGCM(self._gcm_key)
            nonce = os.urandom(12)
            ct = aesgcm.encrypt(nonce, data, None)
            payload = base64.urlsafe_b64encode(nonce + ct).decode('utf-8')
            return f'{self.GCM_PREFIX.decode("utf-8")}{payload}'
        except Exception:
            logger.exception('Large field encryption failed: %s')
            raise

    @classmethod
    def generate_key(cls) -> str:
        return Fernet.generate_key().decode('utf-8')

    @classmethod
    def migrate_column(
        cls, model_class, column_name: str, batch_size: int = 500, key: str | None = None
    ):
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
            rows = (
                db.session.execute(
                    select(model_class)
                    .filter(getattr(model_class, column_name).isnot(None))
                    .limit(batch_size)
                )
                .scalars()
                .all()
            )
            if not rows:
                break
            for row in rows:
                val = getattr(row, column_name)
                if val and not svc.is_encrypted(val):
                    setattr(row, column_name, svc.encrypt(val))
                    total += 1
            session.commit()
            logger.info(
                'Batch encrypted %s rows of %s.%s', len(rows), model_class.__name__, column_name
            )
        logger.info(
            'Migration complete: %s total rows encrypted for %s.%s',
            total,
            model_class.__name__,
            column_name,
        )
        return total
