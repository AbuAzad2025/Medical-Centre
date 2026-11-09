"""Coverage tests for the low-coverage service modules.

Targets: services/lab_service.py, services/notification_service.py,
services/pricing_service.py, services/core_queries.py,
services/queue_management_service.py, services/nursing_service.py,
services/field_encryption_service.py, services/tenant_job_runner.py.

Everything here asserts real behaviour against the test database (savepoint
isolation via ``rollback_db``) or real round-trip contracts for the crypto
primitives. Exact-count assertions that cannot tolerate shared rows use a
freshly created user or, where practical, deltas.
"""

import uuid

import pytest

# ----------------------------------------------------------------------------- helpers


def _uid():
    return uuid.uuid4().hex[:8]


def _make_patient(db, first_name='Cover', last_name='Patient'):
    from models.patient import Patient

    p = Patient(first_name=first_name, last_name=last_name)
    db.session.add(p)
    db.session.commit()
    return p


def _make_visit(db, patient_id=None, **kw):
    from models.visit import Visit

    v = Visit(patient_id=patient_id or _make_patient(db).id, **kw)
    db.session.add(v)
    db.session.commit()
    return v


def _make_user(db, role='doctor', department_id=None, full_name='Cover User'):
    from models.user import User

    uname = f'cov_{role}_{_uid()}'
    u = User(
        username=uname,
        email=f'{uname}@test.local',
        full_name=full_name,
        role=role,
        is_active=True,
        department_id=department_id,
    )
    u.set_password('test123')
    db.session.add(u)
    db.session.commit()
    return u


def _make_department(db, name=None, name_ar=None):
    from models.department import Department

    tag = _uid()
    d = Department(
        name=name or f'Dept-{tag}',
        name_ar=name_ar or f'قسم-{tag}',
        is_active=True,
    )
    db.session.add(d)
    db.session.commit()
    return d


def _make_lab_catalog(db, **kw):
    from models.lab_test_catalog import LabTestCatalog

    cat = LabTestCatalog(
        code=kw.pop('code', f'C{_uid()}'),
        name_ar=kw.pop('name_ar', 'تحليل'),
        name_en=kw.pop('name_en', 'Cover Test'),
        unit=kw.pop('unit', 'mg/dL'),
        is_active=kw.pop('is_active', True),
        **kw,
    )
    db.session.add(cat)
    db.session.commit()
    return cat


@pytest.fixture
def lab_fx(rollback_db):
    db = rollback_db

    def _patient():
        return _make_patient(db)

    def _visit(patient_id=None, **kw):
        return _make_visit(db, patient_id=patient_id, **kw)

    def _doctor():
        return _make_user(db, role='doctor')

    def _catalog(**kw):
        return _make_lab_catalog(db, **kw)

    return types_ns(db=db, patient=_patient, visit=_visit, doctor=_doctor, catalog=_catalog)


def types_ns(**kw):
    import types

    return types.SimpleNamespace(**kw)


# =====================================================================
# field_encryption_service
# =====================================================================


class TestFieldEncryptionPrimitives:
    @pytest.fixture(autouse=True)
    def _key(self, monkeypatch):
        from cryptography.fernet import Fernet

        monkeypatch.setenv('FIELD_ENCRYPTION_KEY', Fernet.generate_key().decode())
        from services.field_encryption_service import FieldEncryptionService

        # the class caches a singleton keyed on the previous env value; drop it
        FieldEncryptionService._svc_instance = None
        FieldEncryptionService._last_key = None
        yield
        FieldEncryptionService._svc_instance = None
        FieldEncryptionService._last_key = None

    def _svc(self):
        from services.field_encryption_service import FieldEncryptionService

        return FieldEncryptionService()

    def test_encrypt_returns_ciphertext_with_gcm_prefix(self):
        svc = self._svc()
        ct = svc.encrypt('secret-value')
        assert ct.startswith('$gcm$')
        assert 'secret-value' not in ct

    def test_encrypt_empty_and_none_passthrough(self):
        svc = self._svc()
        assert svc.encrypt(None) is None
        assert svc.encrypt('') == ''
        assert svc.encrypt_large(None) is None
        assert svc.encrypt_large('') == ''
        assert svc.encrypt_random(None) is None
        assert svc.encrypt_random('') == ''

    def test_encrypt_large_roundtrip(self):
        svc = self._svc()
        payload = 'x' * 5000
        ct = svc.encrypt_large(payload)
        assert ct.startswith('$gcm$')
        assert svc.decrypt(ct) == payload

    def test_encrypt_random_roundtrip_and_prefix(self):
        svc = self._svc()
        ct = svc.encrypt_random('random-secret')
        assert ct.startswith('$gcm$')
        assert svc.decrypt(ct) == 'random-secret'

    def test_encrypt_deterministic_delegates_to_encrypt(self):
        svc = self._svc()
        ct = svc.encrypt_deterministic('det-value')
        assert ct.startswith('$gcm$')
        assert svc.decrypt(ct) == 'det-value'

    def test_encrypt_is_already_encrypted_passthroughs(self):
        svc = self._svc()
        ct = svc.encrypt('roundtrip me')
        assert svc.encrypt(ct) == ct
        assert svc.encrypt_large(ct) == ct
        assert svc.encrypt_random(ct) == ct

    def test_decrypt_legacy_fernet_roundtrip(self):
        svc = self._svc()
        token = svc._fernet.encrypt(b'legacy-plaintext')
        legacy = '$enc$' + token.decode('utf-8')
        assert svc.decrypt(legacy) == 'legacy-plaintext'
        assert svc.is_encrypted(legacy) is True

    def test_decrypt_plaintext_returned_as_is(self):
        svc = self._svc()
        assert svc.decrypt('plain value') == 'plain value'
        assert svc.decrypt(b'bytes plain') == 'bytes plain'

    def test_decrypt_corrupted_gcm_returns_raw_to_not_break_reads(self):
        svc = self._svc()
        ct = svc.encrypt('top secret')
        corrupted = ct[:-6] + 'AAAAAA'
        assert svc.decrypt(corrupted) == corrupted

    def test_can_decrypt_matrix(self):
        svc = self._svc()
        assert svc.can_decrypt(None) is True
        assert svc.can_decrypt('') is True
        assert svc.can_decrypt('plain') is True
        good = svc.encrypt('data')
        assert svc.can_decrypt(good) is True
        bad = good[:-6] + 'AAAAAA'
        assert svc.can_decrypt(bad) is False
        legacy = '$enc$' + svc._fernet.encrypt(b'old').decode('utf-8')
        assert svc.can_decrypt(legacy) is True
        assert svc.can_decrypt('$enc$not-a-valid-token') is False

    def test_searchable_roundtrip_is_deterministic(self):
        svc = self._svc()
        a = svc.encrypt_searchable('National-123')
        b = svc.encrypt_searchable('National-123')
        assert a == b
        assert a.startswith('$siv$')
        assert svc.decrypt_searchable(a) == 'National-123'

    def test_searchable_upgrades_legacy_ciphertext(self):
        svc = self._svc()
        legacy = svc.encrypt('migrate-me')
        siv = svc.encrypt_searchable(legacy)
        assert siv.startswith('$siv$')
        assert svc.decrypt_searchable(siv) == 'migrate-me'

    def test_searchable_idempotent_on_own_ciphertext(self):
        svc = self._svc()
        siv = svc.encrypt_searchable('once')
        assert svc.encrypt_searchable(siv) == siv

    def test_searchable_empty_passthrough(self):
        svc = self._svc()
        assert svc.encrypt_searchable(None) is None
        assert svc.encrypt_searchable('') == ''
        assert svc.decrypt_searchable(None) is None
        assert svc.decrypt_searchable('') == ''

    def test_decrypt_searchable_falls_back_to_decrypt_for_gcm(self):
        svc = self._svc()
        ct = svc.encrypt('plain-in-gcm')
        assert svc.decrypt_searchable(ct) == 'plain-in-gcm'

    def test_decrypt_searchable_corrupted_returns_input(self):
        svc = self._svc()
        bad = '$siv$' + 'A' * 40
        assert svc.decrypt_searchable(bad) == bad

    def test_blind_index_properties(self):
        svc = self._svc()
        h1 = svc.blind_index('patient-42')
        assert h1 == svc.blind_index('patient-42')
        assert h1 != svc.blind_index('patient-43')
        assert len(h1) == 64
        assert svc.blind_index(None) is None
        assert svc.blind_index('') is None
        assert svc.blind_index(b'bytes-input') == svc.blind_index('bytes-input')

    def test_hash_for_lookup_alias_matches_blind_index(self):
        svc = self._svc()
        assert svc.hash_for_lookup('alias') == svc.blind_index('alias')

    def test_is_encrypted_and_searchable_encrypted(self):
        svc = self._svc()
        gcm = svc.encrypt('v')
        siv = svc.encrypt_searchable('v')
        assert svc.is_encrypted(gcm) is True
        assert svc.is_encrypted(siv) is True
        assert svc.is_encrypted('nope') is False
        assert svc.is_encrypted(None) is False
        assert svc.is_encrypted(b'nope') is False
        assert svc.is_searchable_encrypted(siv) is True
        assert svc.is_searchable_encrypted(gcm) is False
        assert svc.is_searchable_encrypted('nope') is False
        assert svc.is_searchable_encrypted(None) is False

    def test_get_service_returns_none_on_invalid_key_and_recovers(self, monkeypatch):
        from services import field_encryption_service as fes

        monkeypatch.setenv('FIELD_ENCRYPTION_KEY', 'not-a-fernet-key')
        fes.FieldEncryptionService._svc_instance = None
        fes.FieldEncryptionService._last_key = None
        assert fes.FieldEncryptionService.get_service() is None
        assert fes.FieldEncryptionService.is_active() is False

        from cryptography.fernet import Fernet

        monkeypatch.setenv('FIELD_ENCRYPTION_KEY', Fernet.generate_key().decode())
        fes.FieldEncryptionService._svc_instance = None
        fes.FieldEncryptionService._last_key = None
        assert fes.FieldEncryptionService.get_service() is not None
        assert fes.FieldEncryptionService.is_active() is True

    def test_get_service_caches_when_key_unchanged(self):
        from services import field_encryption_service as fes

        svc1 = fes.FieldEncryptionService.get_service()
        svc2 = fes.FieldEncryptionService.get_service()
        assert svc1 is svc2

    def test_generate_key_roundtrip(self):
        from cryptography.fernet import Fernet

        from services import field_encryption_service as fes

        key = fes.FieldEncryptionService.generate_key()
        # the generated key must be usable to construct a service
        Fernet(key.encode('utf-8'))
        svc = fes.FieldEncryptionService(key=key)
        assert svc.decrypt(svc.encrypt('abc')) == 'abc'

    def test_missing_key_raises(self, monkeypatch):
        from services import field_encryption_service as fes

        monkeypatch.delenv('FIELD_ENCRYPTION_KEY', raising=False)
        with pytest.raises(fes.EncryptionConfigurationError):
            fes.FieldEncryptionService()

    def test_invalid_key_raises(self):
        from services import field_encryption_service as fes

        with pytest.raises(fes.EncryptionConfigurationError):
            fes.FieldEncryptionService(key='not-a-valid-key')


class TestFieldEncryptionMigration:
    @pytest.fixture(autouse=True)
    def _key(self, monkeypatch):
        from cryptography.fernet import Fernet

        self._key = Fernet.generate_key().decode()
        monkeypatch.setenv('FIELD_ENCRYPTION_KEY', self._key)

    def test_migrate_column_encrypts_plaintext_rows(self, rollback_db, monkeypatch):
        from services import field_encryption_service as fes

        db = rollback_db
        plaintext_national_id = f'{_uid()}MIG'

        # Write the row with no key configured: at-rest it is plaintext, as a
        # legacy database would have it.
        monkeypatch.delenv('FIELD_ENCRYPTION_KEY', raising=False)
        patient = _make_patient(db, first_name='Mig', last_name='Rate')
        patient.national_id = plaintext_national_id
        db.session.commit()

        from models.patient import Patient

        # Now run the migration with a key configured.
        monkeypatch.setenv('FIELD_ENCRYPTION_KEY', self._key)
        total = fes.FieldEncryptionService.migrate_column(
            Patient, 'national_id', batch_size=1, key=self._key
        )
        assert total >= 1

        from sqlalchemy import text

        raw = db.session.execute(
            text('SELECT national_id FROM patients WHERE id = :id'), {'id': patient.id}
        ).scalar()
        assert raw.startswith(('$gcm$', '$enc$', '$siv$'))
        assert fes.FieldEncryptionService(key=self._key).decrypt(raw) == plaintext_national_id
