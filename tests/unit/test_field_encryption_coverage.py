"""Coverage tests for services/field_encryption_service.py.

Real crypto round-trips against freshly generated keys, plus behaviour against
the test database (savepoint isolation via ``rollback_db``) for the one-time
column migration helper.

One defect is characterised here on purpose: ``FieldEncryptionService.migrate_column``
re-selects the same non-null rows on every iteration and never excludes rows
it already encrypted (the ORM transparently decrypts on read, so the stored
ciphertext never looks encrypted to the ``is_encrypted`` guard). Once any
non-null row exists the loop never terminates. The migration tests below prove
the empty-table path returns 0 and exercise the row-processing path with a
hard commit cap that aborts the runaway loop — see
``test_migrate_column_row_path_does_not_terminate``. The bug is reported, not
fixed, here.
"""

import base64
import uuid

import pytest


def _uid():
    return uuid.uuid4().hex[:8]


@pytest.fixture
def key_env(monkeypatch):
    """Fresh Fernet key in the environment; singletons reset before/after."""
    from cryptography.fernet import Fernet

    from services import field_encryption_service as fes

    def _reset():
        fes.FieldEncryptionService._svc_instance = None
        fes.FieldEncryptionService._last_key = None

    _reset()
    key = Fernet.generate_key().decode()
    monkeypatch.setenv('FIELD_ENCRYPTION_KEY', key)
    yield key
    _reset()


@pytest.fixture
def svc(key_env):
    from services import field_encryption_service as fes

    return fes.FieldEncryptionService()


def _fresh_key():
    from cryptography.fernet import Fernet

    return Fernet.generate_key().decode()


# =====================================================================
# Construction / configuration
# =====================================================================


class TestConfiguration:
    def test_missing_key_raises_with_guidance(self, monkeypatch):
        from services import field_encryption_service as fes

        monkeypatch.delenv('FIELD_ENCRYPTION_KEY', raising=False)
        fes.FieldEncryptionService._svc_instance = None
        fes.FieldEncryptionService._last_key = None
        with pytest.raises(fes.EncryptionConfigurationError) as excinfo:
            fes.FieldEncryptionService()
        assert 'FIELD_ENCRYPTION_KEY' in str(excinfo.value)
        assert 'Fernet' in str(excinfo.value)

    def test_invalid_fernet_key_raises(self):
        from services import field_encryption_service as fes

        with pytest.raises(fes.EncryptionConfigurationError) as excinfo:
            fes.FieldEncryptionService(key='not-a-fernet-key')
        assert 'Invalid FIELD_ENCRYPTION_KEY' in str(excinfo.value)

    def test_error_message_chains_original_exception(self):
        from services import field_encryption_service as fes

        with pytest.raises(fes.EncryptionConfigurationError) as excinfo:
            fes.FieldEncryptionService(key='!!!')
        assert excinfo.value.__cause__ is not None

    def test_constructor_strips_surrounding_whitespace(self):
        from cryptography.fernet import Fernet

        from services import field_encryption_service as fes

        raw = Fernet.generate_key().decode()
        svc = fes.FieldEncryptionService(key=f'  {raw}  ')
        assert svc._raw_key == raw

    def test_blank_key_argument_raises(self, monkeypatch):
        from services import field_encryption_service as fes

        monkeypatch.setenv('FIELD_ENCRYPTION_KEY', '   ')
        with pytest.raises(fes.EncryptionConfigurationError):
            fes.FieldEncryptionService()

    def test_repeated_construction_uses_gcm_and_derived_caches(self, key_env):
        from services import field_encryption_service as fes

        first = fes.FieldEncryptionService(key=key_env)
        second = fes.FieldEncryptionService(key=key_env)
        assert first._gcm_key == second._gcm_key
        assert first._siv_key == second._siv_key
        assert first._blind_key == second._blind_key
        # the raw key really is cached on the class, not re-derived
        assert key_env in fes.FieldEncryptionService._gcm_cache
        assert key_env in fes.FieldEncryptionService._derived_cache

    def test_distinct_keys_derive_distinct_primitives(self):
        from services import field_encryption_service as fes

        key_a, key_b = _fresh_key(), _fresh_key()
        svc_a = fes.FieldEncryptionService(key=key_a)
        svc_b = fes.FieldEncryptionService(key=key_b)
        assert svc_a._gcm_key != svc_b._gcm_key
        assert svc_a._siv_key != svc_b._siv_key
        assert svc_a._blind_key != svc_b._blind_key


# =====================================================================
# Singleton / key rotation
# =====================================================================


class TestSingleton:
    def test_get_service_caches_instance_per_key(self, key_env):
        from services import field_encryption_service as fes

        svc1 = fes.FieldEncryptionService.get_service()
        svc2 = fes.FieldEncryptionService.get_service()
        assert svc1 is svc2

    def test_get_service_rebuilds_when_key_changes(self, key_env, monkeypatch):
        from services import field_encryption_service as fes

        first = fes.FieldEncryptionService.get_service()
        rotated = _fresh_key()
        monkeypatch.setenv('FIELD_ENCRYPTION_KEY', rotated)
        second = fes.FieldEncryptionService.get_service()
        assert second is not first
        assert second._raw_key == rotated

    def test_get_service_returns_none_when_key_becomes_invalid(self, key_env, monkeypatch):
        from services import field_encryption_service as fes

        assert fes.FieldEncryptionService.get_service() is not None
        monkeypatch.setenv('FIELD_ENCRYPTION_KEY', 'garbage-key')
        assert fes.FieldEncryptionService.get_service() is None
        assert fes.FieldEncryptionService.is_active() is False

    def test_get_service_returns_none_when_key_removed(self, key_env, monkeypatch):
        from services import field_encryption_service as fes

        assert fes.FieldEncryptionService.get_service() is not None
        monkeypatch.delenv('FIELD_ENCRYPTION_KEY', raising=False)
        assert fes.FieldEncryptionService.get_service() is None
        assert fes.FieldEncryptionService.is_active() is False

    def test_get_service_recovers_after_invalid_key(self, key_env, monkeypatch):
        from services import field_encryption_service as fes

        monkeypatch.setenv('FIELD_ENCRYPTION_KEY', 'garbage-key')
        fes.FieldEncryptionService._svc_instance = None
        fes.FieldEncryptionService._last_key = None
        assert fes.FieldEncryptionService.get_service() is None
        monkeypatch.setenv('FIELD_ENCRYPTION_KEY', _fresh_key())
        assert fes.FieldEncryptionService.get_service() is not None

    def test_is_active_true_with_valid_key(self, key_env):
        from services import field_encryption_service as fes

        assert fes.FieldEncryptionService.is_active() is True


# =====================================================================
# encrypt / decrypt (AES-256-GCM, random nonce)
# =====================================================================


class TestEncryptDecrypt:
    def test_roundtrip_str(self, svc):
        ct = svc.encrypt('sensitive بيانات')
        assert ct.startswith('$gcm$')
        assert svc.decrypt(ct) == 'sensitive بيانات'

    def test_roundtrip_bytes_input_utf8_payload(self, svc):
        ct = svc.encrypt('بيانات-123'.encode())
        assert ct.startswith('$gcm$')
        assert svc.decrypt(ct) == 'بيانات-123'

    def test_decrypt_of_non_utf8_payload_returns_raw_ciphertext(self, svc):
        # The primitive accepts arbitrary bytes on encrypt, but ``decrypt``
        # must produce a ``str`` and decodes with UTF-8 only; a non-UTF-8
        # payload therefore fails to decode and is returned unchanged (the
        # raw ciphertext), exactly like any other decrypt failure.
        payload = b'\x00\x01binary-\xff'
        ct = svc.encrypt(payload)
        assert svc.decrypt(ct) == ct

    def test_roundtrip_bytes_ciphertext_input(self, svc):
        ct = svc.encrypt('bytes-ct')
        assert svc.decrypt(ct.encode('utf-8')) == 'bytes-ct'

    def test_same_plaintext_yields_different_ciphertext(self, svc):
        assert svc.encrypt('repeat') != svc.encrypt('repeat')

    def test_encrypt_none_and_empty_passthrough(self, svc):
        assert svc.encrypt(None) is None
        assert svc.encrypt('') == ''

    def test_encrypt_already_encrypted_is_not_double_wrapped(self, svc):
        ct = svc.encrypt('once')
        assert svc.encrypt(ct) == ct
        assert svc.encrypt(ct.encode()) == ct

    def test_encrypt_legacy_prefixed_value_returned_as_is(self, svc):
        legacy = '$enc$sometoken'
        assert svc.encrypt(legacy) == legacy

    def test_decrypt_none_and_empty_passthrough(self, svc):
        assert svc.decrypt(None) is None
        assert svc.decrypt('') == ''

    def test_decrypt_plaintext_passthrough_str_and_bytes(self, svc):
        assert svc.decrypt('open text') == 'open text'
        assert svc.decrypt(b'open bytes') == 'open bytes'

    def test_decrypt_legacy_fernet_roundtrip(self, svc):
        token = svc._fernet.encrypt(b'legacy-plaintext')
        legacy = '$enc$' + token.decode('utf-8')
        assert svc.decrypt(legacy) == 'legacy-plaintext'
        assert svc.decrypt(legacy.encode()) == 'legacy-plaintext'

    def test_decrypt_corrupted_gcm_returns_raw_input(self, svc):
        ct = svc.encrypt('payload')
        corrupted = ct[:-4] + 'AAAA'
        assert svc.decrypt(corrupted) == corrupted
        assert svc.decrypt(corrupted.encode()) == corrupted

    def test_decrypt_gcm_with_valid_base64_but_short_payload_returns_raw(self, svc):
        short = '$gcm$' + base64.urlsafe_b64encode(b'short').decode()
        assert svc.decrypt(short) == short

    def test_decrypt_corrupted_legacy_fernet_returns_raw_input(self, svc):
        bad = '$enc$not-a-fernet-token'
        assert svc.decrypt(bad) == bad
        assert svc.decrypt(bad.encode()) == bad

    def test_decrypt_tampered_legacy_returns_raw_input(self, svc):
        token = svc._fernet.encrypt(b'original')
        legacy = '$enc$' + token.decode('utf-8')
        tampered = legacy[:-4] + 'AAAA'
        assert svc.decrypt(tampered) == tampered

    def test_encrypt_propagates_aesgcm_failure(self, svc, monkeypatch):
        from services import field_encryption_service as fes

        class _Boom:
            def __init__(self, *args, **kwargs):
                pass

            def encrypt(self, *args, **kwargs):
                raise ValueError('gcm boom')

        monkeypatch.setattr(fes, 'AESGCM', _Boom)
        with pytest.raises(ValueError, match='gcm boom'):
            svc.encrypt('data')


# =====================================================================
# encrypt_large / encrypt_random / encrypt_deterministic
# =====================================================================


class TestLargeAndRandom:
    def test_encrypt_large_roundtrip(self, svc):
        payload = 'لاين-' * 2000
        ct = svc.encrypt_large(payload)
        assert ct.startswith('$gcm$')
        assert svc.decrypt(ct) == payload

    def test_encrypt_large_bytes(self, svc):
        ct = svc.encrypt_large(b'\x89PNG-large-\x00' * 100)
        assert ct.startswith('$gcm$')

    def test_encrypt_large_none_and_empty_passthrough(self, svc):
        assert svc.encrypt_large(None) is None
        assert svc.encrypt_large('') == ''

    def test_encrypt_large_already_encrypted_passthrough(self, svc):
        ct = svc.encrypt_large('big secret')
        assert svc.encrypt_large(ct) == ct
        legacy = '$enc$token'
        assert svc.encrypt_large(legacy) == legacy

    def test_encrypt_large_propagates_aesgcm_failure(self, svc, monkeypatch):
        from services import field_encryption_service as fes

        class _Boom:
            def __init__(self, *args, **kwargs):
                pass

            def encrypt(self, *args, **kwargs):
                raise RuntimeError('large boom')

        monkeypatch.setattr(fes, 'AESGCM', _Boom)
        with pytest.raises(RuntimeError, match='large boom'):
            svc.encrypt_large('payload')

    def test_encrypt_random_roundtrip(self, svc):
        ct = svc.encrypt_random('random secret')
        assert ct.startswith('$gcm$')
        assert svc.decrypt(ct) == 'random secret'
        assert svc.encrypt_random('x') != svc.encrypt_random('x')

    def test_encrypt_random_bytes(self, svc):
        ct = svc.encrypt_random(b'\x00\x01\x02')
        assert ct.startswith('$gcm$')

    def test_encrypt_random_none_and_empty_passthrough(self, svc):
        assert svc.encrypt_random(None) is None
        assert svc.encrypt_random('') == ''

    def test_encrypt_random_already_encrypted_passthrough(self, svc):
        ct = svc.encrypt_random('secret')
        assert svc.encrypt_random(ct) == ct

    def test_encrypt_random_propagates_aesgcm_failure(self, svc, monkeypatch):
        from services import field_encryption_service as fes

        class _Boom:
            def __init__(self, *args, **kwargs):
                pass

            def encrypt(self, *args, **kwargs):
                raise RuntimeError('random boom')

        monkeypatch.setattr(fes, 'AESGCM', _Boom)
        with pytest.raises(RuntimeError, match='random boom'):
            svc.encrypt_random('payload')

    def test_encrypt_deterministic_delegates_to_encrypt_not_siv(self, svc):
        # Contract as implemented: a thin alias of the randomised ``encrypt``,
        # NOT the deterministic searchable primitive. Identical plaintexts
        # therefore produce different ciphertexts.
        ct1 = svc.encrypt_deterministic('det')
        ct2 = svc.encrypt_deterministic('det')
        assert ct1.startswith('$gcm$')
        assert not ct1.startswith('$siv$')
        assert ct1 != ct2
        assert svc.decrypt(ct1) == 'det'


# =====================================================================
# Searchable encryption (AES-SIV, deterministic)
# =====================================================================


class TestSearchable:
    def test_roundtrip_str(self, svc):
        siv = svc.encrypt_searchable('National-0001')
        assert siv.startswith('$siv$')
        assert svc.decrypt_searchable(siv) == 'National-0001'

    def test_deterministic_for_identical_plaintext(self, svc):
        assert svc.encrypt_searchable('same-value') == svc.encrypt_searchable('same-value')

    def test_bytes_plaintext_roundtrip(self, svc):
        siv = svc.encrypt_searchable(b'bytes-plain')
        assert siv.startswith('$siv$')
        assert svc.decrypt_searchable(siv) == 'bytes-plain'

    def test_none_and_empty_passthrough(self, svc):
        assert svc.encrypt_searchable(None) is None
        assert svc.encrypt_searchable('') == ''
        assert svc.decrypt_searchable(None) is None
        assert svc.decrypt_searchable('') == ''

    def test_already_siv_value_returned_verbatim(self, svc):
        siv = svc.encrypt_searchable('once')
        assert svc.encrypt_searchable(siv) == siv
        assert svc.encrypt_searchable(siv.encode()) == siv

    def test_gcm_ciphertext_is_upgraded_to_searchable(self, svc):
        gcm = svc.encrypt('upgrade-me')
        siv = svc.encrypt_searchable(gcm)
        assert siv.startswith('$siv$')
        assert svc.decrypt_searchable(siv) == 'upgrade-me'

    def test_gcm_bytes_ciphertext_is_upgraded(self, svc):
        gcm = svc.encrypt('upgrade-bytes')
        siv = svc.encrypt_searchable(gcm.encode())
        assert siv.startswith('$siv$')
        assert svc.decrypt_searchable(siv) == 'upgrade-bytes'

    def test_legacy_fernet_ciphertext_is_upgraded(self, svc):
        token = svc._fernet.encrypt(b'legacy-searchable')
        legacy = '$enc$' + token.decode('utf-8')
        siv = svc.encrypt_searchable(legacy)
        assert siv.startswith('$siv$')
        assert svc.decrypt_searchable(siv) == 'legacy-searchable'

    def test_undecryptable_gcm_input_is_re_encrypted_verbatim(self, svc):
        # Current behaviour: an input with a GCM prefix that cannot be
        # decrypted comes back from ``decrypt`` unchanged and is then
        # re-encrypted as-is; it does not raise and does not return None.
        broken = '$gcm$corrupted-payload'
        siv = svc.encrypt_searchable(broken)
        assert siv.startswith('$siv$')
        assert svc.decrypt_searchable(siv) == broken

    def test_upgrade_returns_none_when_decrypt_returns_none(self, svc, monkeypatch):
        monkeypatch.setattr(svc, 'decrypt', lambda _value: None)
        gcm = svc.encrypt('never-reached')
        assert svc.encrypt_searchable(gcm) is None

    def test_encrypt_searchable_propagates_siv_failure(self, svc, monkeypatch):
        from services import field_encryption_service as fes

        class _Boom:
            def __init__(self, *args, **kwargs):
                pass

            def encrypt(self, *args, **kwargs):
                raise ValueError('siv boom')

        monkeypatch.setattr(fes, 'AESSIV', _Boom)
        with pytest.raises(ValueError, match='siv boom'):
            svc.encrypt_searchable('data')

    def test_decrypt_searchable_accepts_bytes(self, svc):
        siv = svc.encrypt_searchable('bytes-in')
        assert svc.decrypt_searchable(siv.encode()) == 'bytes-in'

    def test_decrypt_searchable_falls_back_for_plaintext(self, svc):
        assert svc.decrypt_searchable('plain value') == 'plain value'
        assert svc.decrypt_searchable(b'plain bytes') == 'plain bytes'

    def test_decrypt_searchable_falls_back_for_gcm(self, svc):
        gcm = svc.encrypt('gcm-in-siv-slot')
        assert svc.decrypt_searchable(gcm) == 'gcm-in-siv-slot'

    def test_decrypt_searchable_corrupted_returns_input(self, svc):
        bad = '$siv$' + 'A' * 44
        assert svc.decrypt_searchable(bad) == bad
        assert svc.decrypt_searchable(bad.encode()) == bad


# =====================================================================
# Blind index (HMAC-SHA256)
# =====================================================================


class TestBlindIndex:
    def test_deterministic_and_keyed(self, svc):
        assert svc.blind_index('patient-1') == svc.blind_index('patient-1')
        assert svc.blind_index('patient-1') != svc.blind_index('patient-2')

    def test_output_is_64_hex_chars(self, svc):
        digest = svc.blind_index('shape')
        assert len(digest) == 64
        int(digest, 16)

    def test_none_and_empty_yield_none(self, svc):
        assert svc.blind_index(None) is None
        assert svc.blind_index('') is None

    def test_str_and_bytes_inputs_agree(self, svc):
        assert svc.blind_index(b'raw-bytes') == svc.blind_index('raw-bytes')

    def test_unicode_input(self, svc):
        a = svc.blind_index('مريض-١٢٣')
        b = svc.blind_index('مريض-١٢٣')
        assert a == b

    def test_hash_for_lookup_is_blind_index_alias(self, svc):
        assert svc.hash_for_lookup('alias') == svc.blind_index('alias')
        assert svc.hash_for_lookup(None) is None

    def test_blind_index_changes_with_key(self):
        from services import field_encryption_service as fes

        svc_a = fes.FieldEncryptionService(key=_fresh_key())
        svc_b = fes.FieldEncryptionService(key=_fresh_key())
        assert svc_a.blind_index('same') != svc_b.blind_index('same')


# =====================================================================
# can_decrypt / is_encrypted / is_searchable_encrypted
# =====================================================================


class TestInspectionHelpers:
    def test_can_decrypt_none_and_empty(self, svc):
        assert svc.can_decrypt(None) is True
        assert svc.can_decrypt('') is True

    def test_can_decrypt_plaintext_rows(self, svc):
        assert svc.can_decrypt('plain') is True
        assert svc.can_decrypt(b'plain bytes') is True

    def test_can_decrypt_valid_gcm(self, svc):
        ct = svc.encrypt('check me')
        assert svc.can_decrypt(ct) is True
        assert svc.can_decrypt(ct.encode()) is True

    def test_can_decrypt_corrupted_gcm(self, svc):
        ct = svc.encrypt('check me')
        bad = ct[:-4] + 'AAAA'
        assert svc.can_decrypt(bad) is False
        assert svc.can_decrypt(bad.encode()) is False

    def test_can_decrypt_gcm_with_valid_base64_but_short_payload(self, svc):
        short = '$gcm$' + base64.urlsafe_b64encode(b'short').decode()
        assert svc.can_decrypt(short) is False

    def test_can_decrypt_valid_legacy_fernet(self, svc):
        legacy = '$enc$' + svc._fernet.encrypt(b'old').decode('utf-8')
        assert svc.can_decrypt(legacy) is True
        assert svc.can_decrypt(legacy.encode()) is True

    def test_can_decrypt_corrupted_legacy_fernet(self, svc):
        assert svc.can_decrypt('$enc$not-a-token') is False

    def test_can_decrypt_siv_value_reports_true(self, svc):
        # Current behaviour: ``can_decrypt`` only inspects the LEGACY and GCM
        # prefixes, so an AES-SIV value (which ``decrypt`` cannot actually
        # decrypt) reports True. Characterised so the contract is explicit.
        siv = svc.encrypt_searchable('v')
        assert svc.can_decrypt(siv) is True

    def test_is_encrypted_matrix(self, svc):
        gcm = svc.encrypt('v')
        siv = svc.encrypt_searchable('v')
        legacy = '$enc$token'
        assert svc.is_encrypted(gcm) is True
        assert svc.is_encrypted(siv) is True
        assert svc.is_encrypted(legacy) is True
        assert svc.is_encrypted('nope') is False
        assert svc.is_encrypted('') is False
        assert svc.is_encrypted(None) is False
        assert svc.is_encrypted(gcm.encode()) is True
        assert svc.is_encrypted(siv.encode()) is True
        assert svc.is_encrypted(b'nope') is False

    def test_is_searchable_encrypted_matrix(self, svc):
        siv = svc.encrypt_searchable('v')
        gcm = svc.encrypt('v')
        assert svc.is_searchable_encrypted(siv) is True
        assert svc.is_searchable_encrypted(siv.encode()) is True
        assert svc.is_searchable_encrypted(gcm) is False
        assert svc.is_searchable_encrypted('nope') is False
        assert svc.is_searchable_encrypted(None) is False


# =====================================================================
# generate_key
# =====================================================================


class TestGenerateKey:
    def test_generated_key_is_valid_fernet_key(self):
        from cryptography.fernet import Fernet

        from services import field_encryption_service as fes

        key = fes.FieldEncryptionService.generate_key()
        assert isinstance(key, str)
        raw = base64.urlsafe_b64decode(key.encode('utf-8'))
        assert len(raw) == 32
        Fernet(key.encode('utf-8'))  # must not raise

    def test_generated_keys_are_unique(self):
        from services import field_encryption_service as fes

        assert (
            fes.FieldEncryptionService.generate_key() != fes.FieldEncryptionService.generate_key()
        )

    def test_generated_key_constructs_working_service(self):
        from services import field_encryption_service as fes

        svc = fes.FieldEncryptionService(key=fes.FieldEncryptionService.generate_key())
        assert svc.decrypt(svc.encrypt('roundtrip')) == 'roundtrip'


# =====================================================================
# migrate_column (one-time batch encryption)
# =====================================================================


def _temp_encrypted_model(db, table_name):
    """Map a throwaway model onto a TEMP table with an EncryptedString column."""
    from sqlalchemy import Column, Integer, MetaData, Table, text
    from sqlalchemy.orm import declarative_base

    from app.shared.encrypted_type import EncryptedString

    db.session.execute(text(f'CREATE TEMP TABLE {table_name} (id serial primary key, secret text)'))
    table = Table(
        table_name,
        MetaData(),
        Column('id', Integer, primary_key=True),
        Column('secret', EncryptedString(), nullable=True),
    )

    class _Probe(declarative_base()):
        __table__ = table
        __tablename__ = table_name

    return _Probe


class TestMigrateColumn:
    def test_empty_table_returns_zero(self, rollback_db, monkeypatch):
        from services import field_encryption_service as fes

        key = _fresh_key()
        monkeypatch.setenv('FIELD_ENCRYPTION_KEY', key)
        table = f'mig_probe_{_uid()}'
        model = _temp_encrypted_model(rollback_db, table)

        total = fes.FieldEncryptionService.migrate_column(model, 'secret', batch_size=5, key=None)
        assert total == 0

    def test_row_path_does_not_terminate(self, rollback_db, monkeypatch):
        """Characterise a real defect in ``migrate_column``.

        The loop re-selects the same non-null rows forever: the ORM decrypts
        on read, so the ``is_encrypted`` guard never skips, and nothing narrows
        the result set between iterations. With one plaintext row present the
        migration encrypts it, then keeps "migrating" the same row forever
        (each pass decrypts -> re-encrypts -> increments ``total``).

        We cap the run at a few ``commit`` calls and assert the row ends up
        stored as GCM ciphertext — proving the row-processing path works and
        that the loop itself never exits on its own.
        """

        from sqlalchemy import text

        from services import field_encryption_service as fes

        monkeypatch.delenv('FIELD_ENCRYPTION_KEY', raising=False)
        table = f'mig_probe_{_uid()}'
        model = _temp_encrypted_model(rollback_db, table)

        # Written with no key configured: stored as plaintext, as a legacy row.
        probe = model(secret='plaintext-to-migrate')
        rollback_db.session.add(probe)
        rollback_db.session.commit()

        key = _fresh_key()
        monkeypatch.setenv('FIELD_ENCRYPTION_KEY', key)

        class _MigrationLoopGuardError(RuntimeError):
            pass

        original_commit = rollback_db.session.commit
        calls = {'n': 0}

        def _capped_commit():
            calls['n'] += 1
            if calls['n'] > 3:
                raise _MigrationLoopGuardError
            return original_commit()

        monkeypatch.setattr(rollback_db.session, 'commit', _capped_commit)

        with pytest.raises(_MigrationLoopGuardError):
            fes.FieldEncryptionService.migrate_column(model, 'secret', batch_size=1, key=key)

        assert calls['n'] > 3  # the loop wanted to keep going long after the row was encrypted
        raw = rollback_db.session.execute(text(f'SELECT secret FROM {table}')).scalar()
        assert raw.startswith('$gcm$')

    def test_falsy_value_rows_are_skipped_but_loop_still_spins(self, rollback_db, monkeypatch):
        """A selected row with a falsy value takes the ``if val and ...`` skip,
        so ``total`` never advances — yet the row keeps being re-selected, so
        the loop still never terminates. Characterised with the commit cap."""

        from sqlalchemy import text

        from services import field_encryption_service as fes

        monkeypatch.delenv('FIELD_ENCRYPTION_KEY', raising=False)
        table = f'mig_probe_{_uid()}'
        model = _temp_encrypted_model(rollback_db, table)

        rollback_db.session.add(model(secret=''))
        rollback_db.session.commit()

        key = _fresh_key()
        monkeypatch.setenv('FIELD_ENCRYPTION_KEY', key)

        class _MigrationLoopGuardError(RuntimeError):
            pass

        original_commit = rollback_db.session.commit
        calls = {'n': 0}

        def _capped_commit():
            calls['n'] += 1
            if calls['n'] > 3:
                raise _MigrationLoopGuardError
            return original_commit()

        monkeypatch.setattr(rollback_db.session, 'commit', _capped_commit)

        with pytest.raises(_MigrationLoopGuardError):
            fes.FieldEncryptionService.migrate_column(model, 'secret', batch_size=1, key=key)

        raw = rollback_db.session.execute(text(f'SELECT secret FROM {table}')).scalar()
        assert raw == ''
