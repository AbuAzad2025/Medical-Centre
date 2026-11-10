"""Service-level coverage for services/nursing_service.py.

Complements tests/test_nursing_service.py: every public method and every
branch that is reachable against the migrated test database is exercised
here through the real service code and a real database round trip.

Notes on reachability (tested, not fabricated):

- ``models.nurse`` has no ``NursingNote`` model anywhere in the codebase or
  in migrations, so ``get_notes`` / ``add_note`` normally degrade to ``[]`` /
  ``None`` by their ``except Exception`` fallback. The success paths of those
  two functions are nevertheless real service code, so a test-local
  ``nursing_notes`` table and model are injected (``nursing_notes_model``
  fixture) and exercised through the same code path. The table is created
  inside the ``rollback_db`` outer transaction and is dropped when that
  transaction rolls back, so the shared test database is left untouched.
- ``services.nursing_service.safe_commit`` is monkeypatched to ``False`` in a
  few tests to cover the commit-failure branches without touching the
  database.
- ``services.nursing_service.get_tenant_record`` is monkeypatched to raise a
  non-tenant exception to cover the ``except Exception`` fallbacks that the
  ``TenantContextError`` tests cannot reach.

All DB work runs under ``rollback_db`` isolation.
"""

import importlib
import types
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from app.extensions import db
from models.emar import eMARAdministration
from models.medication import Medication
from models.nurse import MedicationAdministrationLog, Nurse
from models.patient import Patient
from models.task_management import Task
from models.user import User
from models.visit import Visit
from services.nursing_service import NursingService as NS
from services.nursing_service import nursing_service

# ``services/__init__.py`` re-exports the ``nursing_service`` singleton under
# the same name as the module, so ``monkeypatch.setattr(_nursing_service_module, 'x')``
# would resolve onto the instance. import_module returns the real module.
_nursing_service_module = importlib.import_module('services.nursing_service')

_SCRUB_ENCRYPTED = """
UPDATE patients SET
    national_id = NULL WHERE national_id LIKE '$gcm$%' OR national_id LIKE '$enc$%';
UPDATE patients SET
    first_name = 'legacy' WHERE first_name LIKE '$gcm$%' OR first_name LIKE '$enc$%';
UPDATE patients SET
    last_name = 'legacy' WHERE last_name LIKE '$gcm$%' OR last_name LIKE '$enc$%';
UPDATE patients SET
    first_name_ar = NULL WHERE first_name_ar LIKE '$gcm$%' OR first_name_ar LIKE '$enc$%';
UPDATE patients SET
    last_name_ar = NULL WHERE last_name_ar LIKE '$gcm$%' OR last_name_ar LIKE '$enc$%';
UPDATE patients SET
    phone = NULL WHERE phone LIKE '$gcm$%' OR phone LIKE '$enc$%';
UPDATE patients SET
    address = NULL WHERE address LIKE '$gcm$%' OR address LIKE '$enc$%';
UPDATE patients SET
    insurance_member_number = NULL
    WHERE insurance_member_number LIKE '$gcm$%' OR insurance_member_number LIKE '$enc$%';
"""


def _uniq(prefix: str) -> str:
    return f'{prefix}_{uuid.uuid4().hex[:10]}'


def _safe_commit_false(*_args, **_kwargs):
    return False


def _noop_add(_record):
    return None


@pytest.fixture
def fx(rollback_db):
    db = rollback_db

    with db.engine.begin() as conn:
        conn.execute(
            text('ALTER TABLE vital_signs ADD COLUMN IF NOT EXISTS blood_sugar DOUBLE PRECISION')
        )
        conn.execute(text(_SCRUB_ENCRYPTED))

    def user(role='nurse'):
        un = _uniq('nsc')
        u = User(username=un, email=f'{un}@x.com', full_name='u', role=role, is_active=True)
        u.set_password('p')
        db.session.add(u)
        db.session.commit()
        return u

    def patient(first_name=None, last_name=None):
        p = Patient(
            first_name=first_name or 'fn' + uuid.uuid4().hex[:6], last_name=last_name or 'ln'
        )
        db.session.add(p)
        db.session.commit()
        return p

    def visit(patient_id=None):
        pid = patient_id or patient().id
        v = Visit(patient_id=pid)
        db.session.add(v)
        db.session.commit()
        return v

    def nurse():
        n = Nurse(user_id=user().id, license_number=_uniq('LN'))
        db.session.add(n)
        db.session.commit()
        return n

    def task(status='pending', assigned_to=None):
        t = Task(
            title='T',
            task_type='patient_care',
            status=status,
            priority='medium',
            assigned_by=user().id,
            assigned_to=assigned_to,
        )
        db.session.add(t)
        db.session.commit()
        return t

    def admin_log(visit_obj, medication_id=None):
        log = MedicationAdministrationLog(
            patient_id=visit_obj.patient_id,
            visit_id=visit_obj.id,
            medication_id=medication_id,
        )
        db.session.add(log)
        db.session.commit()
        return log

    def emar(visit_obj, status='SCHEDULED', medication_id=None):
        # The live emar_administrations table declares medication_id NOT NULL
        # (the model says nullable=True), so always attach a real medication.
        if medication_id is None:
            medication_id = medication().id
        rec = eMARAdministration(
            patient_id=visit_obj.patient_id,
            visit_id=visit_obj.id,
            scheduled_time=datetime.now(UTC),
            status=status,
            medication_id=medication_id,
        )
        db.session.add(rec)
        db.session.commit()
        return rec

    def medication():
        med = Medication(
            scientific_name=_uniq('sci'),
            trade_name=_uniq('trade'),
            dosage_form='tablet',
            strength='500mg',
            price=0,
        )
        db.session.add(med)
        db.session.commit()
        return med

    return types.SimpleNamespace(
        db=db,
        user=user,
        patient=patient,
        visit=visit,
        nurse=nurse,
        task=task,
        admin_log=admin_log,
        emar=emar,
        medication=medication,
    )


class _NursingNoteModel(db.Model):
    """Stand-in for the absent production NursingNote model.

    Defined once at module import time so SQLAlchemy registers it a single
    time. The matching table is created per-test inside the rollback_db
    outer transaction (PostgreSQL DDL is transactional) and disappears with
    the rollback.
    """

    __tablename__ = 'nursing_notes'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    visit_id = db.Column(db.Integer, nullable=False, index=True)
    nurse_id = db.Column(db.Integer, nullable=True)
    content = db.Column(db.Text, nullable=False)
    note_type = db.Column(db.String(50), default='general')
    created_at = db.Column(db.DateTime)


@pytest.fixture
def nursing_notes_model(monkeypatch, fx):
    """Inject a real (transaction-scoped) stand-in for the absent NursingNote.

    The production codebase and its migrations define no NursingNote model,
    so get_notes/add_note can never take their happy path there. To cover
    that real service code honestly, the minimal table backing
    ``_NursingNoteModel`` is created inside the rollback_db outer
    transaction and the service's ``from models.nurse import NursingNote``
    picks the class up via monkeypatch.
    """
    fx.db.session.execute(
        text(
            'CREATE TABLE IF NOT EXISTS nursing_notes ('
            ' id SERIAL PRIMARY KEY,'
            ' visit_id INTEGER NOT NULL,'
            ' nurse_id INTEGER,'
            ' content TEXT NOT NULL,'
            ' note_type VARCHAR(50),'
            ' created_at TIMESTAMP)'
        )
    )
    monkeypatch.setattr('models.nurse.NursingNote', _NursingNoteModel, raising=False)
    return _NursingNoteModel


# --------------------------------------------------------------------------
# get_nurse_patients
# --------------------------------------------------------------------------


class TestGetNursePatients:
    def test_search_matches_created_patient(self, fx):
        token = _uniq('srch')
        p = fx.patient(first_name=token, last_name='findme')
        v = fx.visit(patient_id=p.id)
        results = NS.get_nurse_patients(1, search=token)
        assert any(x.id == v.id for x in results)

    def test_search_no_match_returns_no_such_visit(self, fx):
        p = fx.patient()
        v = fx.visit(patient_id=p.id)
        results = NS.get_nurse_patients(1, search=_uniq('nomatch') + 'zzzz')
        assert all(x.id != v.id for x in results)

    def test_search_exception_returns_empty_list(self, fx, monkeypatch):
        def boom(*args, **kwargs):
            raise RuntimeError('search index unavailable')

        monkeypatch.setattr(Patient, 'search_ids', classmethod(boom))
        assert NS.get_nurse_patients(1, search='anything') == []

    def test_query_exception_returns_empty_list(self, fx, monkeypatch):
        def boom(*args, **kwargs):
            raise RuntimeError('db down')

        monkeypatch.setattr(
            _nursing_service_module,
            'db',
            types.SimpleNamespace(session=types.SimpleNamespace(execute=boom, add=_noop_add)),
        )
        assert NS.get_nurse_patients(1) == []


# --------------------------------------------------------------------------
# get_vitals
# --------------------------------------------------------------------------


class TestGetVitals:
    def test_visit_not_found_returns_empty(self, fx):
        assert NS.get_vitals(99999999) == []

    def test_limit_and_latest_first_ordering(self, fx):
        v = fx.visit()
        n = fx.nurse()
        for temp in (36.5, 37.5, 38.5):
            rec = NS.record_vitals(v.id, recorded_by=n.id, temperature=temp)
            assert rec is not None
        fetched = NS.get_vitals(v.id, limit=2)
        assert len(fetched) == 2
        assert fetched[0].recorded_at >= fetched[1].recorded_at

    def test_unexpected_exception_returns_empty(self, fx, monkeypatch):
        def boom(*args, **kwargs):
            raise RuntimeError('db down')

        monkeypatch.setattr(_nursing_service_module, 'get_tenant_record', boom)
        assert NS.get_vitals(1) == []


# --------------------------------------------------------------------------
# record_vitals - validation branches
# --------------------------------------------------------------------------


class TestRecordVitalsValidation:
    @pytest.mark.parametrize('temperature', [29.9, 45.1, 100])
    def test_temperature_out_of_range(self, fx, temperature):
        v = fx.visit()
        assert NS.record_vitals(v.id, recorded_by=1, temperature=temperature) is None

    @pytest.mark.parametrize('heart_rate', [19, 251])
    def test_heart_rate_out_of_range(self, fx, heart_rate):
        v = fx.visit()
        assert NS.record_vitals(v.id, recorded_by=1, heart_rate=heart_rate) is None

    @pytest.mark.parametrize('systolic', [49, 301])
    def test_systolic_out_of_range(self, fx, systolic):
        v = fx.visit()
        assert NS.record_vitals(v.id, recorded_by=1, blood_pressure_systolic=systolic) is None

    @pytest.mark.parametrize('diastolic', [29, 201])
    def test_diastolic_out_of_range(self, fx, diastolic):
        v = fx.visit()
        assert NS.record_vitals(v.id, recorded_by=1, blood_pressure_diastolic=diastolic) is None

    @pytest.mark.parametrize('rate', [4, 81])
    def test_respiratory_rate_out_of_range(self, fx, rate):
        v = fx.visit()
        assert NS.record_vitals(v.id, recorded_by=1, respiratory_rate=rate) is None

    @pytest.mark.parametrize('oxygen', [49, 101])
    def test_oxygen_saturation_out_of_range(self, fx, oxygen):
        v = fx.visit()
        assert NS.record_vitals(v.id, recorded_by=1, oxygen_saturation=oxygen) is None

    @pytest.mark.parametrize('sugar', [9.9, 800.1])
    def test_blood_sugar_out_of_range(self, fx, sugar):
        v = fx.visit()
        assert NS.record_vitals(v.id, recorded_by=1, blood_sugar=sugar) is None

    def test_diastolic_must_be_below_systolic(self, fx):
        v = fx.visit()
        assert (
            NS.record_vitals(
                v.id,
                recorded_by=1,
                blood_pressure_systolic=120,
                blood_pressure_diastolic=120,
            )
            is None
        )
        assert (
            NS.record_vitals(
                v.id,
                recorded_by=1,
                blood_pressure_systolic=120,
                blood_pressure_diastolic=130,
            )
            is None
        )

    def test_no_values_and_no_notes_returns_none(self, fx):
        v = fx.visit()
        assert NS.record_vitals(v.id, recorded_by=1) is None

    def test_notes_only_is_accepted_and_stripped(self, fx):
        v = fx.visit()
        n = fx.nurse()
        rec = NS.record_vitals(v.id, recorded_by=n.id, notes='  mild headache  ')
        assert rec is not None
        assert rec.notes == 'mild headache'
        assert rec.temperature is None

    def test_oxygen_saturation_is_stored_as_int(self, fx):
        v = fx.visit()
        n = fx.nurse()
        rec = NS.record_vitals(v.id, recorded_by=n.id, oxygen_saturation=97.6)
        assert rec is not None
        assert rec.oxygen_saturation == 97

    def test_visit_not_found_returns_none(self, fx):
        assert NS.record_vitals(99999999, recorded_by=1, temperature=37.0) is None

    def test_commit_failure_returns_none(self, fx, monkeypatch):
        v = fx.visit()
        n = fx.nurse()
        monkeypatch.setattr(_nursing_service_module, 'safe_commit', _safe_commit_false)
        assert NS.record_vitals(v.id, recorded_by=n.id, temperature=37.0) is None
        fx.db.session.rollback()

    def test_unexpected_exception_returns_none(self, fx, monkeypatch):
        def boom(*args, **kwargs):
            raise RuntimeError('db down')

        monkeypatch.setattr(_nursing_service_module, 'get_tenant_record', boom)
        assert NS.record_vitals(1, recorded_by=1, temperature=37.0) is None


# --------------------------------------------------------------------------
# get_notes / add_note
# --------------------------------------------------------------------------


class TestNotesService:
    def test_get_notes_without_model_returns_empty(self, fx):
        # No NursingNote model in the codebase or migrations -> degraded path.
        assert NS.get_notes(1) == []

    def test_add_note_without_model_returns_none(self, fx):
        assert NS.add_note(1, 1, 'content') is None

    def test_add_note_empty_content_returns_none(self, fx, nursing_notes_model):
        assert NS.add_note(1, 1, '') is None
        assert NS.add_note(1, 1, '   ') is None

    def test_add_note_success_stripped_and_typed(self, fx, nursing_notes_model):
        v = fx.visit()
        n = fx.nurse()
        note = NS.add_note(v.id, n.id, '  patient stable  ', note_type='progress')
        assert note is not None
        assert note.content == 'patient stable'
        assert note.note_type == 'progress'
        assert note.nurse_id == n.id

    def test_add_note_default_note_type(self, fx, nursing_notes_model):
        v = fx.visit()
        n = fx.nurse()
        note = NS.add_note(v.id, n.id, 'hello')
        assert note is not None
        assert note.note_type == 'general'

    def test_get_notes_returns_newest_first_and_respects_limit(self, fx, nursing_notes_model):
        v = fx.visit()
        n = fx.nurse()
        for i in range(3):
            rec = nursing_notes_model(
                visit_id=v.id,
                nurse_id=n.id,
                content=f'note {i}',
                note_type='general',
                created_at=datetime(2026, 1, 1, 10, i, tzinfo=UTC),
            )
            fx.db.session.add(rec)
        fx.db.session.commit()
        notes = NS.get_notes(v.id, limit=2)
        assert len(notes) == 2
        assert notes[0].created_at >= notes[1].created_at
        assert {x.content for x in NS.get_notes(v.id, limit=10)} == {
            'note 0',
            'note 1',
            'note 2',
        }

    def test_get_notes_scoped_to_visit(self, fx, nursing_notes_model):
        v1, v2 = fx.visit(), fx.visit()
        n = fx.nurse()
        NS.add_note(v1.id, n.id, 'for visit one')
        assert NS.get_notes(v2.id) == []

    def test_add_note_commit_failure_returns_none(self, fx, nursing_notes_model, monkeypatch):
        v = fx.visit()
        n = fx.nurse()
        monkeypatch.setattr(_nursing_service_module, 'safe_commit', _safe_commit_false)
        assert NS.add_note(v.id, n.id, 'will not commit') is None
        fx.db.session.rollback()

    def test_add_note_unexpected_exception_returns_none(self, fx, nursing_notes_model, monkeypatch):
        def boom(*args, **kwargs):
            raise RuntimeError('db down')

        rolled_back = []
        fake_session = types.SimpleNamespace(add=boom, rollback=lambda: rolled_back.append(True))
        monkeypatch.setattr(
            _nursing_service_module, 'db', types.SimpleNamespace(session=fake_session)
        )
        assert NS.add_note(1, 1, 'content') is None
        assert rolled_back == [True]

    def test_get_notes_unexpected_exception_returns_empty(
        self, fx, nursing_notes_model, monkeypatch
    ):
        def boom(*args, **kwargs):
            raise RuntimeError('db down')

        monkeypatch.setattr(
            _nursing_service_module,
            'db',
            types.SimpleNamespace(session=types.SimpleNamespace(execute=boom)),
        )
        assert NS.get_notes(1) == []


# --------------------------------------------------------------------------
# get_pending_administrations
# --------------------------------------------------------------------------


class TestPendingAdministrations:
    def test_no_visit_id_returns_all_logs(self, fx):
        v1, v2 = fx.visit(), fx.visit()
        log1, log2 = fx.admin_log(v1), fx.admin_log(v2)
        results = NS.get_pending_administrations()
        ids = {x.id for x in results}
        assert log1.id in ids and log2.id in ids

    def test_visit_id_filters(self, fx):
        v1, v2 = fx.visit(), fx.visit()
        log1, log2 = fx.admin_log(v1), fx.admin_log(v2)
        results = NS.get_pending_administrations(v1.id)
        ids = {x.id for x in results}
        assert log1.id in ids and log2.id not in ids

    def test_visit_not_found_returns_empty(self, fx):
        assert NS.get_pending_administrations(99999999) == []

    def test_unexpected_exception_returns_empty(self, fx, monkeypatch):
        monkeypatch.setattr('models.nurse.MedicationAdministrationLog', object())
        assert NS.get_pending_administrations() == []


# --------------------------------------------------------------------------
# record_administration
# --------------------------------------------------------------------------


class TestRecordAdministration:
    def test_not_found_returns_false(self, fx):
        assert NS.record_administration(99999999, nurse_id=1) is False

    def test_notes_stripped(self, fx):
        v = fx.visit()
        n = fx.nurse()
        log = fx.admin_log(v)
        assert NS.record_administration(log.id, nurse_id=n.id, notes='  given po  ') is True
        assert db.session.get(MedicationAdministrationLog, log.id).notes == 'given po'

    def test_notes_none_clears_notes(self, fx):
        v = fx.visit()
        n = fx.nurse()
        log = fx.admin_log(v)
        NS.record_administration(log.id, nurse_id=n.id, notes='something')
        assert NS.record_administration(log.id, nurse_id=n.id, notes=None) is True
        assert db.session.get(MedicationAdministrationLog, log.id).notes is None

    def test_commit_failure_returns_false(self, fx, monkeypatch):
        v = fx.visit()
        log = fx.admin_log(v)
        monkeypatch.setattr(_nursing_service_module, 'safe_commit', _safe_commit_false)
        assert NS.record_administration(log.id, nurse_id=1, notes='x') is False
        fx.db.session.rollback()

    def test_unexpected_exception_returns_false(self, fx, monkeypatch):
        def boom(*args, **kwargs):
            raise RuntimeError('db down')

        monkeypatch.setattr(_nursing_service_module, 'get_tenant_record', boom)
        assert NS.record_administration(1, nurse_id=1) is False


# --------------------------------------------------------------------------
# record_emar_administration
# --------------------------------------------------------------------------


class TestRecordEmarAdministration:
    def test_not_found_returns_failure(self, fx):
        result = NS.record_emar_administration(99999999, nurse_id=1)
        assert result['success'] is False
        assert result['message']

    def test_status_defaults_to_given(self, fx):
        v = fx.visit()
        rec = fx.emar(v, status='SCHEDULED')
        result = NS.record_emar_administration(rec.id, nurse_id=fx.user().id, status=None)
        assert result == {'success': True}
        fx.db.session.expire_all()
        assert db.session.get(eMARAdministration, rec.id).status == 'GIVEN'

    def test_status_is_case_insensitive_and_stripped(self, fx):
        v = fx.visit()
        rec = fx.emar(v, status='SCHEDULED')
        result = NS.record_emar_administration(rec.id, nurse_id=fx.user().id, status='  given  ')
        assert result == {'success': True}

    def test_invalid_status_returns_failure(self, fx):
        v = fx.visit()
        rec = fx.emar(v, status='SCHEDULED')
        result = NS.record_emar_administration(rec.id, nurse_id=fx.user().id, status='BOGUS')
        assert result['success'] is False

    def test_patient_id_mismatch_returns_failure(self, fx):
        v = fx.visit()
        rec = fx.emar(v, status='SCHEDULED')
        result = NS.record_emar_administration(
            rec.id, nurse_id=fx.user().id, patient_id=rec.patient_id + 1000
        )
        assert result['success'] is False

    def test_patient_id_match_is_accepted(self, fx):
        v = fx.visit()
        rec = fx.emar(v, status='SCHEDULED')
        result = NS.record_emar_administration(
            rec.id, nurse_id=fx.user().id, patient_id=rec.patient_id
        )
        assert result == {'success': True}

    def test_medication_id_mismatch_returns_failure(self, fx):
        v = fx.visit()
        med = fx.medication()
        rec = fx.emar(v, status='SCHEDULED', medication_id=med.id)
        result = NS.record_emar_administration(
            rec.id, nurse_id=fx.user().id, medication_id=med.id + 1000
        )
        assert result['success'] is False

    def test_medication_id_match_is_accepted(self, fx):
        v = fx.visit()
        med = fx.medication()
        rec = fx.emar(v, status='SCHEDULED', medication_id=med.id)
        result = NS.record_emar_administration(rec.id, nurse_id=fx.user().id, medication_id=med.id)
        assert result == {'success': True}

    def test_terminal_status_record_is_rejected(self, fx):
        v = fx.visit()
        rec = fx.emar(v, status='GIVEN')
        result = NS.record_emar_administration(rec.id, nurse_id=fx.user().id, status='GIVEN')
        assert result['success'] is False

    def test_given_requires_scheduled_current(self, fx):
        v = fx.visit()
        rec = fx.emar(v, status='LATE')
        result = NS.record_emar_administration(rec.id, nurse_id=fx.user().id, status='GIVEN')
        assert result['success'] is False

    def test_given_success_sets_fields_and_strips_notes(self, fx):
        v = fx.visit()
        u = fx.user()
        rec = fx.emar(v, status='SCHEDULED')
        result = NS.record_emar_administration(
            rec.id, nurse_id=u.id, status='GIVEN', notes='  taken with water  '
        )
        assert result == {'success': True}
        fx.db.session.expire_all()
        updated = db.session.get(eMARAdministration, rec.id)
        assert updated.status == 'GIVEN'
        assert updated.administered_time is not None
        assert updated.nurse_id == u.id
        assert updated.notes == 'taken with water'

    def test_refused_missing_reason_returns_failure(self, fx):
        v = fx.visit()
        rec = fx.emar(v, status='SCHEDULED')
        result = NS.record_emar_administration(rec.id, nurse_id=fx.user().id, status='REFUSED')
        assert result['success'] is False

    def test_refused_accepts_notes_as_reason(self, fx):
        v = fx.visit()
        u = fx.user()
        rec = fx.emar(v, status='SCHEDULED')
        result = NS.record_emar_administration(
            rec.id, nurse_id=u.id, status='REFUSED', notes='patient declined'
        )
        assert result == {'success': True}
        fx.db.session.expire_all()
        updated = db.session.get(eMARAdministration, rec.id)
        assert updated.status == 'REFUSED'
        assert updated.refusal_reason == 'patient declined'
        assert updated.notes == 'patient declined'
        assert updated.administered_time is not None
        assert updated.nurse_id == u.id

    def test_refused_success_with_explicit_reason(self, fx):
        v = fx.visit()
        u = fx.user()
        rec = fx.emar(v, status='SCHEDULED')
        result = NS.record_emar_administration(
            rec.id,
            nurse_id=u.id,
            status='REFUSED',
            refusal_reason='nausea',
            notes='will retry later',
        )
        assert result == {'success': True}
        fx.db.session.expire_all()
        updated = db.session.get(eMARAdministration, rec.id)
        assert updated.refusal_reason == 'nausea'
        assert updated.notes == 'will retry later'

    def test_refused_requires_scheduled_current(self, fx):
        v = fx.visit()
        rec = fx.emar(v, status='LATE')
        result = NS.record_emar_administration(
            rec.id, nurse_id=fx.user().id, status='REFUSED', refusal_reason='reason'
        )
        assert result['success'] is False

    def test_held_missing_reason_returns_failure(self, fx):
        v = fx.visit()
        rec = fx.emar(v, status='SCHEDULED')
        result = NS.record_emar_administration(rec.id, nurse_id=fx.user().id, status='HELD')
        assert result['success'] is False

    def test_held_success_sets_hold_reason_not_administered_time(self, fx):
        v = fx.visit()
        u = fx.user()
        rec = fx.emar(v, status='SCHEDULED')
        result = NS.record_emar_administration(
            rec.id, nurse_id=u.id, status='HELD', refusal_reason='low blood pressure'
        )
        assert result == {'success': True}
        fx.db.session.expire_all()
        updated = db.session.get(eMARAdministration, rec.id)
        assert updated.status == 'HELD'
        assert updated.hold_reason == 'low blood pressure'
        assert updated.nurse_id == u.id
        assert updated.administered_time is None

    def test_held_success_with_notes(self, fx):
        v = fx.visit()
        u = fx.user()
        rec = fx.emar(v, status='SCHEDULED')
        result = NS.record_emar_administration(
            rec.id,
            nurse_id=u.id,
            status='HELD',
            refusal_reason='low BP',
            notes='  recheck in 1h  ',
        )
        assert result == {'success': True}
        fx.db.session.expire_all()
        updated = db.session.get(eMARAdministration, rec.id)
        assert updated.notes == 'recheck in 1h'

    def test_held_requires_scheduled_current(self, fx):
        v = fx.visit()
        rec = fx.emar(v, status='LATE')
        result = NS.record_emar_administration(
            rec.id, nurse_id=fx.user().id, status='HELD', refusal_reason='reason'
        )
        assert result['success'] is False

    def test_other_valid_status_uses_generic_path(self, fx):
        v = fx.visit()
        u = fx.user()
        rec = fx.emar(v, status='SCHEDULED')
        result = NS.record_emar_administration(
            rec.id, nurse_id=u.id, status='PARTIAL', notes='  half dose  '
        )
        assert result == {'success': True}
        fx.db.session.expire_all()
        updated = db.session.get(eMARAdministration, rec.id)
        assert updated.status == 'PARTIAL'
        assert updated.nurse_id == u.id
        assert updated.notes == 'half dose'

    def test_commit_failure_returns_failure_message(self, fx, monkeypatch):
        v = fx.visit()
        rec = fx.emar(v, status='SCHEDULED')
        monkeypatch.setattr(_nursing_service_module, 'safe_commit', _safe_commit_false)
        result = NS.record_emar_administration(rec.id, nurse_id=fx.user().id, status='GIVEN')
        assert result['success'] is False
        fx.db.session.rollback()

    def test_unexpected_exception_returns_failure(self, fx, monkeypatch):
        def boom(*args, **kwargs):
            raise RuntimeError('db down')

        monkeypatch.setattr(_nursing_service_module, 'get_tenant_record', boom)
        result = NS.record_emar_administration(1, nurse_id=1)
        assert result['success'] is False


# --------------------------------------------------------------------------
# get_care_plans / create_care_plan
# --------------------------------------------------------------------------


class TestCarePlans:
    def test_get_care_plans_visit_not_found_returns_empty(self, fx):
        assert NS.get_care_plans(99999999) == []

    def test_get_care_plans_returns_created_plans(self, fx):
        v = fx.visit()
        u = fx.user()
        plan = NS.create_care_plan(v.id, created_by=u.id, plan_type='Recovery', description='rest')
        assert plan is not None
        results = NS.get_care_plans(v.id)
        assert any(x.id == plan.id for x in results)
        # A different visit id yields no plans for this visit.
        other = fx.visit()
        assert all(x.visit_id == other.id for x in NS.get_care_plans(other.id))

    def test_get_care_plans_unexpected_exception_returns_empty(self, fx, monkeypatch):
        def boom(*args, **kwargs):
            raise RuntimeError('db down')

        monkeypatch.setattr(_nursing_service_module, 'get_tenant_record', boom)
        assert NS.get_care_plans(1) == []

    def test_create_care_plan_blank_plan_type_returns_none(self, fx):
        v = fx.visit()
        assert NS.create_care_plan(v.id, created_by=1, plan_type='', description='d') is None
        assert NS.create_care_plan(v.id, created_by=1, plan_type='   ', description='d') is None

    def test_create_care_plan_blank_description_returns_none(self, fx):
        v = fx.visit()
        assert NS.create_care_plan(v.id, created_by=1, plan_type='p', description='') is None
        assert NS.create_care_plan(v.id, created_by=1, plan_type='p', description='   ') is None

    def test_create_care_plan_visit_not_found_returns_none(self, fx):
        assert (
            NS.create_care_plan(99999999, created_by=fx.user().id, plan_type='p', description='d')
            is None
        )

    def test_create_care_plan_strips_fields_and_sets_status(self, fx):
        v = fx.visit()
        u = fx.user()
        plan = NS.create_care_plan(
            v.id, created_by=u.id, plan_type='  Recovery  ', description='  rest  ', goals='x'
        )
        assert plan is not None
        assert plan.plan_name == 'Recovery'
        assert plan.notes == 'rest'
        assert plan.status == 'ACTIVE'
        assert plan.assigned_by_id == u.id
        assert plan.patient_id == v.patient_id

    def test_create_care_plan_commit_failure_returns_none(self, fx, monkeypatch):
        v = fx.visit()
        monkeypatch.setattr(_nursing_service_module, 'safe_commit', _safe_commit_false)
        assert NS.create_care_plan(v.id, created_by=1, plan_type='p', description='d') is None
        fx.db.session.rollback()

    def test_create_care_plan_unexpected_exception_returns_none(self, fx, monkeypatch):
        def boom(*args, **kwargs):
            raise RuntimeError('db down')

        monkeypatch.setattr(_nursing_service_module, 'get_tenant_record', boom)
        assert NS.create_care_plan(1, created_by=1, plan_type='p', description='d') is None


# --------------------------------------------------------------------------
# get_pending_tasks / complete_task
# --------------------------------------------------------------------------


class TestTasks:
    def test_get_pending_tasks_excludes_cancelled(self, fx):
        cancelled = fx.task(status='cancelled')
        pending = fx.task(status='pending')
        ids = {t.id for t in NS.get_pending_tasks()}
        assert pending.id in ids
        assert cancelled.id not in ids

    def test_get_pending_tasks_unexpected_exception_returns_empty(self, fx, monkeypatch):
        monkeypatch.setattr('models.task_management.Task', object())
        assert NS.get_pending_tasks() == []

    def test_complete_task_not_found_returns_false(self, fx):
        assert NS.complete_task(99999999, completed_by=1) is False

    def test_complete_task_already_completed_returns_false(self, fx):
        t = fx.task(status='completed')
        assert NS.complete_task(t.id, completed_by=1) is False

    def test_complete_task_commit_failure_returns_false(self, fx, monkeypatch):
        t = fx.task(status='pending')
        monkeypatch.setattr(_nursing_service_module, 'safe_commit', _safe_commit_false)
        assert NS.complete_task(t.id, completed_by=1) is False
        fx.db.session.rollback()

    def test_complete_task_unexpected_exception_returns_false(self, fx, monkeypatch):
        def boom(*args, **kwargs):
            raise RuntimeError('db down')

        monkeypatch.setattr(_nursing_service_module, 'get_tenant_record', boom)
        assert NS.complete_task(1, completed_by=1) is False


# --------------------------------------------------------------------------
# get_dashboard_stats
# --------------------------------------------------------------------------


class TestDashboardStats:
    def test_unexpected_exception_returns_zero_stats(self, fx, monkeypatch):
        def boom(*args, **kwargs):
            raise RuntimeError('db down')

        monkeypatch.setattr(NS, 'get_nurse_patients', boom)
        assert NS.get_dashboard_stats(1) == {
            'assigned_patients': 0,
            'pending_tasks': 0,
            'pending_administrations': 0,
        }

    def test_singleton_instance_uses_same_code_path(self, fx):
        stats = nursing_service.get_dashboard_stats(1)
        assert set(stats) == {'assigned_patients', 'pending_tasks', 'pending_administrations'}
