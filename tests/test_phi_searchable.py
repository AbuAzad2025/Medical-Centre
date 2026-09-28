"""Regression tests for searchable / enforceable PHI.

These run with FIELD_ENCRYPTION_KEY set, which the rest of the suite never does
(tests/conftest.py pops it). That is the point: the defects guarded here were
invisible to CI precisely because CI exercised the plaintext fallback.

Covers:
  * deterministic (AES-SIV) and blind-index primitives
  * automatic digest maintenance on insert and update
  * exact lookups by national id / phone / name
  * normalisation (case, whitespace, Arabic-Indic digits)
  * database-enforced uniqueness per tenant
  * RLS isolation of the digests
"""

from __future__ import annotations

import base64
import uuid

import pytest

KEY = 's_M_Z3Ce6kEET1m2G9SnxzSJHOx91uetbhcFTJB_KIc='


@pytest.fixture(autouse=True)
def _encryption_on(monkeypatch):
    """Enable field encryption for these tests only."""
    from cryptography.fernet import Fernet

    monkeypatch.setenv('FIELD_ENCRYPTION_KEY', Fernet.generate_key().decode())
    from services.field_encryption_service import FieldEncryptionService

    FieldEncryptionService._svc_instance = None
    FieldEncryptionService._last_key = None
    FieldEncryptionService._gcm_cache.clear()
    FieldEncryptionService._derived_cache.clear()
    yield
    FieldEncryptionService._svc_instance = None
    FieldEncryptionService._last_key = None
    FieldEncryptionService._gcm_cache.clear()
    FieldEncryptionService._derived_cache.clear()


def _svc():
    from services.field_encryption_service import FieldEncryptionService

    return FieldEncryptionService.get_service()


def _skip_if_rls_bypassed(db) -> None:
    """Skip a test that asserts RLS when the connected role bypasses it.

    A superuser or a role with BYPASSRLS sees every row regardless of
    app.tenant_id, so an assertion that a tenant-less connection sees nothing
    cannot hold there. The dedicated RLS job runs as a restricted role, which is
    where these assertions are actually meaningful.
    """
    from sqlalchemy import text

    bypass = db.session.execute(
        text('select rolbypassrls or rolsuper from pg_roles where rolname = current_user')
    ).scalar()
    if bypass:
        pytest.skip('connected role bypasses RLS, so isolation cannot be asserted here')


class TestPrimitives:
    def test_gcm_is_not_deterministic(self):
        svc = _svc()
        assert svc.encrypt('x') != svc.encrypt('x')

    def test_siv_is_deterministic_and_reversible(self):
        svc = _svc()
        a = svc.encrypt_searchable('Sara')
        b = svc.encrypt_searchable('Sara')
        assert a == b, 'searchable encryption must be deterministic'
        assert svc.decrypt_searchable(a) == 'Sara'
        assert svc.encrypt_searchable('\u0633\u0627\u0631\u0629') != a

    def test_siv_output_is_marked_and_differs_from_gcm(self):
        svc = _svc()
        assert svc.encrypt_searchable('x').startswith('$siv$')
        assert svc.encrypt('x').startswith('$gcm$')

    def test_siv_upgrades_legacy_ciphertext_idempotently(self):
        svc = _svc()
        legacy = svc.encrypt('Layla')
        once = svc.encrypt_searchable(legacy)
        assert svc.decrypt_searchable(once) == 'Layla'
        assert svc.encrypt_searchable(once) == once, 'must not re-wrap $siv$ values'

    def test_blind_index_is_stable_and_opaque(self):
        svc = _svc()
        digest = svc.blind_index('123456789')
        assert digest == svc.blind_index('123456789')
        assert digest != svc.blind_index('987654321')
        assert len(digest) == 64 and all(c in '0123456789abcdef' for c in digest)
        assert '123456789' not in digest, 'digest must not contain the plaintext'

    def test_siv_and_blind_index_use_different_keys(self):
        svc = _svc()
        assert svc._siv_key != svc._blind_key
        assert svc._blind_key != svc._gcm_key

    @pytest.mark.parametrize(
        ('a', 'b'),
        [
            ('  Sara ', 'sara'),
            ('Sara-Ahmed', 'saraahmed'),
            ('\u0660\u0661\u0662\u0663', '0123'),
            ('Sara', 'Sara'),
        ],
    )
    def test_normalisation_collapses_cosmetic_differences(self, a, b):
        from app.shared.encrypted_type import blind_index_value, normalize_for_index

        assert normalize_for_index(a) == normalize_for_index(b)
        assert blind_index_value(a) == blind_index_value(b)

    def test_blind_index_is_none_without_a_value(self):
        from app.shared.encrypted_type import blind_index_value

        assert blind_index_value(None) is None
        assert blind_index_value('') is None


# Order matters: rollback_db reconfigures the session, so it must be set up before
# test_tenant loads the Tenant, otherwise the instance is detached.
@pytest.mark.usefixtures('app', 'db', 'rollback_db', 'test_tenant')
class TestPatientBlindIndex:
    @staticmethod
    def _tid(tenant):
        """Capture the id up front: the rollback fixture detaches the instance."""
        return tenant.id

    def _make(self, db, tenant, **kw):
        from models.patient import Patient

        kw.setdefault('first_name', 'Sara')
        kw.setdefault('last_name', 'Ahmed')
        kw.setdefault('gender', 'female')
        p = Patient(tenant_id=self._tid(tenant), **kw)
        db.session.add(p)
        db.session.commit()
        return p

    def test_digests_are_filled_on_insert(self, app, db, test_tenant, rollback_db):
        p = self._make(db, test_tenant, national_id='ID-1', phone='0591112233')
        assert p.national_id_hash and len(p.national_id_hash) == 64
        assert p.phone_hash and len(p.phone_hash) == 64
        assert p.first_name_hash and len(p.first_name_hash) == 64
        assert p.last_name_hash and len(p.last_name_hash) == 64

    def test_digests_are_refreshed_on_update(self, app, db, test_tenant, rollback_db):
        p = self._make(db, test_tenant, national_id='ID-2')
        before = p.national_id_hash
        p.national_id = 'ID-3'
        db.session.commit()
        assert p.national_id_hash != before, 'stale digest breaks duplicate detection'

    def test_ciphertext_is_still_randomised(self, app, db, test_tenant, rollback_db):
        p = self._make(db, test_tenant, national_id='ID-4')
        raw = db.session.execute(
            db.text('select national_id from patients where id = :i'), {'i': p.id}
        ).scalar()
        assert raw.startswith('$gcm$'), 'identity must keep the random-nonce scheme'

    def test_name_column_is_deterministically_encrypted(self, app, db, test_tenant, rollback_db):
        p = self._make(db, test_tenant, national_id='ID-5')
        raw = db.session.execute(
            db.text('select first_name from patients where id = :i'), {'i': p.id}
        ).scalar()
        assert raw.startswith('$siv$'), 'searchable column must use the SIV scheme'

    def test_equal_names_share_ciphertext_so_indexes_are_useful(
        self, app, db, test_tenant, rollback_db
    ):
        a = self._make(db, test_tenant, first_name='Noor', national_id='ID-6')
        self._make(db, test_tenant, first_name='Noor', national_id='ID-7')
        raw = lambda pid: db.session.execute(  # noqa: E731
            db.text('select first_name from patients where id = :i'), {'i': pid}
        ).scalar()
        # Equal plaintext -> equal ciphertext, which is what makes the B-tree
        # index on this column selective instead of indexing random bytes.
        assert raw(a.id) == raw(a.id + 1)

    def test_find_by_national_id(self, app, db, test_tenant, rollback_db):
        from models.patient import Patient

        self._make(db, test_tenant, national_id='ID-8')
        assert Patient.find_by_national_id('ID-8', tenant_id=self._tid(test_tenant)) is not None
        assert Patient.find_by_national_id('NOPE', tenant_id=self._tid(test_tenant)) is None

    def test_find_by_national_id_tolerates_formatting(self, app, db, test_tenant, rollback_db):
        from models.patient import Patient

        self._make(db, test_tenant, national_id='ID-9')
        assert Patient.find_by_national_id(' id-9 ', tenant_id=self._tid(test_tenant)) is not None

    def test_find_by_phone(self, app, db, test_tenant, rollback_db):
        from models.patient import Patient

        self._make(db, test_tenant, phone='0592223344')
        assert Patient.find_by_phone('0592223344', tenant_id=self._tid(test_tenant)) is not None

    @pytest.mark.parametrize(
        ('term', 'expected'),
        [
            ('Sara', 1),
            ('sara', 1),
            ('  SARA ', 1),
            ('Sara Ahmed', 1),
            ('ahmed', 1),
            ('nobody', 0),
            ('', 0),
        ],
    )
    def test_search(self, app, db, test_tenant, rollback_db, term, expected):
        from models.patient import Patient

        self._make(db, test_tenant, first_name='Sara', last_name='Ahmed', national_id='ID-S')
        assert len(Patient.search(term, tenant_id=self._tid(test_tenant))) == expected

    def test_search_finds_arabic_names(self, app, db, test_tenant, rollback_db):
        """Reception searches Arabic names, so the Arabic columns need digests."""
        from models.patient import Patient

        p = self._make(
            db,
            test_tenant,
            first_name='Sara',
            last_name='Ahmed',
            first_name_ar='سارة',
            last_name_ar='أحمد',
            national_id='ID-AR',
        )
        assert p.first_name_ar_hash and len(p.first_name_ar_hash) == 64
        assert p.last_name_ar_hash and len(p.last_name_ar_hash) == 64
        tid = self._tid(test_tenant)
        # Note: normalisation folds Unicode form, Arabic-Indic digits, case and
        # separators. It deliberately does NOT fold distinct Arabic letters
        # (ساره vs سارة are different names), so they must not match.
        for term in ('سارة', 'سارة أحمد', '  سارة  '):
            assert [x.id for x in Patient.search(term, tenant_id=tid)] == [p.id], term
        assert Patient.search('ساره', tenant_id=tid) == []

    def test_arabic_digest_tracks_normalised_digits(self, app, db, test_tenant, rollback_db):
        from models.patient import Patient

        a = self._make(
            db,
            test_tenant,
            first_name_ar='سارة',
            last_name_ar='أحمد',
            national_id='ID-AR1',
        )
        b = self._make(
            db,
            test_tenant,
            first_name_ar='سارة',
            last_name_ar='أحمد',
            national_id='ID-AR2',
        )
        assert a.first_name_ar_hash == b.first_name_ar_hash
        assert [x.id for x in Patient.search('سارة', tenant_id=self._tid(test_tenant))] == sorted(
            [a.id, b.id]
        )

    def test_search_is_tenant_scoped(self, app, db, test_tenant, rollback_db):
        from models.patient import Patient

        self._make(db, test_tenant, first_name='Unique', national_id='ID-T')
        other = uuid.uuid4().int % 100000
        assert Patient.search('Unique', tenant_id=self._tid(test_tenant) + other) == []

    def test_database_rejects_duplicate_national_id(self, app, db, test_tenant, rollback_db):
        from sqlalchemy.exc import IntegrityError

        from models.patient import Patient

        self._make(db, test_tenant, national_id='ID-DUP', phone='0593333444')
        with pytest.raises(IntegrityError):
            db.session.add(
                Patient(
                    first_name='Other',
                    last_name='Person',
                    national_id='ID-DUP',
                    phone='0595556677',
                    gender='male',
                    tenant_id=self._tid(test_tenant),
                )
            )
            db.session.commit()
        db.session.rollback()

    def test_same_national_id_allowed_in_another_tenant(self, app, db, test_tenant, rollback_db):
        from app.core.tenant.middleware import bind_g_tenant
        from app.core.tenant.models import Tenant
        from models.patient import Patient

        self._make(db, test_tenant, national_id='ID-SHARED')
        other = Tenant(
            name='Other Clinic',
            slug=f'other-{uuid.uuid4().hex[:8]}',
            status='active',
            contact_email='other@example.test',
        )
        db.session.add(other)
        db.session.commit()
        # Writing for another tenant requires that tenant to be bound; RLS
        # rejecting the row otherwise is the isolation guarantee working.
        bind_g_tenant(other)
        try:
            dup = Patient(
                first_name='Second',
                last_name='Clinic',
                national_id='ID-SHARED',
                phone='0597778899',
                gender='male',
                tenant_id=other.id,
            )
            db.session.add(dup)
            db.session.commit()
            assert dup.id is not None
        finally:
            bind_g_tenant(test_tenant)

    def test_digests_are_not_readable_without_a_tenant(self, app, db, test_tenant, rollback_db):
        """RLS must still hide everything when no tenant is bound."""
        from sqlalchemy import text

        _skip_if_rls_bypassed(db)
        self._make(db, test_tenant, national_id='ID-RLS')
        with db.engine.connect() as conn:
            conn.execute(text("select set_config('app.tenant_id', '', false)"))
            n = conn.execute(
                text('select count(*) from patients where national_id_hash is not null')
            ).scalar()
            conn.rollback()
        assert n == 0


# Order matters: rollback_db reconfigures the session, so it must be set up
# before test_tenant loads the Tenant, otherwise the instance is detached.
@pytest.mark.usefixtures('app', 'db', 'rollback_db', 'test_tenant')
class TestSubstringSearch:
    """Substring search over encrypted columns, via the blind trigram index.

    This is what replaces the ``ILIKE '%term%'`` queries that silently returned
    nothing once the columns were encrypted.
    """

    def test_partial_name_is_found(self, db, test_tenant):
        from models.patient import Patient

        p = self._make(db, test_tenant, first_name='Sara', last_name='Ahmed', national_id='ID-S1')
        tid = self._tid(test_tenant)
        # Real substrings of "sara"/"ahmed", each at least NGRAM characters.
        for term in ('sar', 'ara', 'Sara', 'hme', 'med', 'Ahmed'):
            assert [x.id for x in Patient.search(term, tenant_id=tid)] == [p.id], term

    def test_partial_arabic_name_is_found(self, db, test_tenant):
        from models.patient import Patient

        p = self._make(
            db,
            test_tenant,
            first_name='Sara',
            last_name='Ahmed',
            first_name_ar='سارة',
            last_name_ar='أحمد',
            national_id='ID-S2',
        )
        tid = self._tid(test_tenant)
        for term in ('ارة', 'أحم', 'سارة'):
            assert [x.id for x in Patient.search(term, tenant_id=tid)] == [p.id], term

    def test_no_false_positive_when_trigrams_are_not_contiguous(self, db, test_tenant):
        """Both trigrams of "abcd" exist in "abcbcd" but it is not a substring.

        Only the decrypt-and-re-check phase catches this, so it is the assertion
        that proves the index is not just a trigram bucket.
        """
        from models.patient import Patient

        trap = self._make(db, test_tenant, first_name='abcbcd', last_name='x', national_id='ID-S3')
        tid = self._tid(test_tenant)
        assert [x.id for x in Patient.search('abcd', tenant_id=tid)] == []
        assert trap.id not in [x.id for x in Patient.search('abcd', tenant_id=tid)]

    def test_missing_term_returns_nothing(self, db, test_tenant):
        from models.patient import Patient

        self._make(db, test_tenant, first_name='Sara', last_name='Ahmed', national_id='ID-S4')
        tid = self._tid(test_tenant)
        assert Patient.search('Zzzzz', tenant_id=tid) == []

    def test_term_shorter_than_a_trigram_finds_nothing(self, db, test_tenant):
        """Documented limitation, pinned so it cannot regress silently.

        A two-character term has no trigram to index, so substring search cannot
        see it. Reporting that honestly is better than pretending to search.
        """
        from app.shared import search_index
        from models.patient import Patient

        self._make(db, test_tenant, first_name='Sara', last_name='Ahmed', national_id='ID-S5')
        tid = self._tid(test_tenant)
        assert search_index.is_indexable('Sa') is False
        assert search_index.is_indexable('Sar') is True
        assert Patient.search('Sa', tenant_id=tid) == []

    def test_rename_drops_the_old_trigrams(self, db, test_tenant):
        from models.patient import Patient

        p = self._make(db, test_tenant, first_name='Sara', last_name='Ahmed', national_id='ID-S6')
        tid = self._tid(test_tenant)
        assert [x.id for x in Patient.search('Sara', tenant_id=tid)] == [p.id]
        p.first_name = 'Zainab'
        db.session.commit()
        assert Patient.search('Sara', tenant_id=tid) == []
        assert [x.id for x in Patient.search('Zainab', tenant_id=tid)] == [p.id]

    def test_ngram_rows_are_scoped_to_the_tenant(self, db, test_tenant):
        from app.core.tenant.middleware import bind_g_tenant
        from app.core.tenant.models import Tenant
        from models.patient import Patient, PatientSearchNgram

        tid = self._tid(test_tenant)
        self._make(db, test_tenant, first_name='Sara', last_name='Ahmed', national_id='ID-S7')
        # Read while this tenant is still bound: RLS hides the other tenant's
        # rows by design, so the count has to be taken before switching.
        mine = (
            db.session.execute(
                db.select(PatientSearchNgram).where(PatientSearchNgram.tenant_id == tid)
            )
            .scalars()
            .all()
        )
        assert mine, 'expected trigram rows for the first tenant'
        assert all(r.tenant_id == tid for r in mine)

        other = Tenant(
            name='Ngram Other',
            slug=f'ngram-{uuid.uuid4().hex[:8]}',
            status='active',
            contact_email='ngram@example.test',
        )
        db.session.add(other)
        db.session.commit()
        bind_g_tenant(other)
        try:
            # Same name, different tenant: must not be reachable from the first.
            assert Patient.search('Sara', tenant_id=other.id) == []
        finally:
            bind_g_tenant(test_tenant)

    def test_ngram_table_is_hidden_without_a_tenant(self, db, rollback_db, test_tenant):
        from sqlalchemy import text

        _skip_if_rls_bypassed(db)
        self._make(db, test_tenant, first_name='Sara', last_name='Ahmed', national_id='ID-S8')
        with db.engine.connect() as conn:
            conn.execute(text("select set_config('app.tenant_id', '', false)"))
            n = conn.execute(text('select count(*) from patient_search_ngrams')).scalar()
            conn.rollback()
        assert n == 0

    def test_ngram_digest_is_separate_from_the_blind_index(self):
        """A leaked n-gram digest must not confirm a value via the blind index."""
        from app.shared.encrypted_type import blind_index_value
        from app.shared.search_index import ngram_digest

        assert ngram_digest('sara') != blind_index_value('sara')
        assert ngram_digest('sara') == ngram_digest('sara')

    @staticmethod
    def _make(db, tenant, **kw):
        from models.patient import Patient

        kw.setdefault('gender', 'female')
        p = Patient(tenant_id=tenant.id, **kw)
        db.session.add(p)
        db.session.commit()
        return p

    @staticmethod
    def _tid(tenant):
        return tenant.id


@pytest.mark.usefixtures('app', 'db', 'rollback_db', 'test_tenant')
class TestUnencryptedFallback:
    """Without a key the columns hold plaintext.

    The blind index is then NULL, so a digest-only lookup would match nothing
    and would silently switch duplicate detection off in development and CI --
    which is exactly how this regression reached a green local run first.
    """

    @pytest.fixture(autouse=True)
    def _encryption_off(self, monkeypatch):
        from services.field_encryption_service import FieldEncryptionService

        monkeypatch.delenv('FIELD_ENCRYPTION_KEY', raising=False)
        FieldEncryptionService._svc_instance = None
        FieldEncryptionService._last_key = None
        FieldEncryptionService._gcm_cache.clear()
        FieldEncryptionService._derived_cache.clear()
        yield
        FieldEncryptionService._svc_instance = None
        FieldEncryptionService._last_key = None
        FieldEncryptionService._gcm_cache.clear()
        FieldEncryptionService._derived_cache.clear()

    @staticmethod
    def _make(db, tenant_id, **kw):
        from models.patient import Patient

        kw.setdefault('first_name', 'Sara')
        kw.setdefault('last_name', 'Ahmed')
        kw.setdefault('gender', 'female')
        p = Patient(tenant_id=tenant_id, **kw)
        db.session.add(p)
        db.session.commit()
        return p

    def test_duplicate_national_id_is_still_detected(self, app, db, test_tenant, rollback_db):
        from models.patient import Patient

        tid = test_tenant.id
        self._make(db, tid, national_id='ID-PLAIN')
        assert Patient.find_by_national_id('ID-PLAIN', tenant_id=tid) is not None
        assert Patient.find_by_national_id('ID-OTHER', tenant_id=tid) is None

    def test_duplicate_phone_is_still_detected(self, app, db, test_tenant, rollback_db):
        from models.patient import Patient

        tid = test_tenant.id
        self._make(db, tid, phone='0591112233')
        assert Patient.find_by_phone('0591112233', tenant_id=tid) is not None
        assert Patient.find_by_phone('0599999999', tenant_id=tid) is None

    def test_search_still_matches_substrings(self, app, db, test_tenant, rollback_db):
        """The unencrypted path keeps the forgiving substring behaviour."""
        from models.patient import Patient

        tid = test_tenant.id
        self._make(db, tid, first_name='Sara', last_name='Ahmed', national_id='ID-PLAIN')
        assert len(Patient.search('Sar', tenant_id=tid)) == 1
        assert len(Patient.search('Sara', tenant_id=tid)) == 1
        assert Patient.search('nobody', tenant_id=tid) == []


class TestSearchableType:
    def test_binds_and_reads_back(self):
        from app.shared.encrypted_type import EncryptedSearchableString

        col = EncryptedSearchableString(200)
        # bind/result processing is dialect-agnostic here.
        bound = col.process_bind_param('Sara', None)
        assert bound.startswith('$siv$')
        assert col.process_result_value(bound, None) == 'Sara'

    def test_passthrough_when_encryption_disabled(self, monkeypatch):
        from app.shared.encrypted_type import EncryptedSearchableString

        monkeypatch.delenv('FIELD_ENCRYPTION_KEY', raising=False)
        from services.field_encryption_service import FieldEncryptionService

        FieldEncryptionService._svc_instance = None
        FieldEncryptionService._last_key = None
        col = EncryptedSearchableString(200)
        assert col.process_bind_param('Sara', None) == 'Sara'

    def test_can_decrypt_rejects_a_ciphertext_from_another_key(self):
        """Rewriting a row whose ciphertext will not open would nest ciphertext
        inside ciphertext and destroy the only copy, so this must be detectable."""
        from cryptography.fernet import Fernet

        from services.field_encryption_service import FieldEncryptionService

        svc = FieldEncryptionService.get_service()
        foreign = Fernet(base64.urlsafe_b64encode(b'x' * 32))  # valid Fernet, wrong key
        # The prefix matters: a prefixed blob is ciphertext, an unprefixed one is
        # a legacy plaintext row that decrypt() deliberately passes through.
        other_key_ct = svc.LEGACY_PREFIX + foreign.encrypt(b'Sara')
        assert svc.can_decrypt(other_key_ct.decode()) is False
        assert svc.can_decrypt(svc.encrypt('Sara')) is True
        assert svc.can_decrypt('plain Sara') is True
        assert svc.can_decrypt(None) is True
        assert svc.can_decrypt(svc.encrypt_searchable('Sara')) is True

    def test_blind_index_raises_instead_of_writing_null(self, monkeypatch):
        """A NULL digest silently disables duplicate detection, so it must not
        be produced while encryption is configured."""
        from app.shared.encrypted_type import blind_index_value
        from services.field_encryption_service import FieldEncryptionService

        assert blind_index_value('Sara')  # works

        def _boom(*_args, **_kwargs):
            raise RuntimeError('boom')

        monkeypatch.setattr(FieldEncryptionService, 'blind_index', _boom)
        try:
            blind_index_value('Sara')
        except ValueError as exc:
            assert 'Blind index' in str(exc)
        else:
            raise AssertionError('expected a loud failure, got a NULL digest')
