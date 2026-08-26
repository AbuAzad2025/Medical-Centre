"""Emergency hardening tests.

Covers:
- prescription POST must persist a real Prescription row via
  PrescriptionService (was a no-op commit + success flash)
- treatment POST / start / end must persist the real emergency_cases
  columns added by p7_006 (were phantom attr writes silently lost)
- regression guard: routes may only write columns that exist on the model
"""

import uuid

import pytest
from sqlalchemy import func, select

from app_factory import db as _db

REAL_TREATMENT_COLUMNS = (
    'treatment_given',
    'medications_text',
    'procedures_text',
    'treated_by_id',
    'treatment_started_at',
    'treatment_completed_at',
    'completed_by_id',
)

PHANTOM_COLUMNS = (
    'medications',
    'procedures',
    'treatment_notes',
    'treated_by',
    'treated_at',
    'completed_by',
    'symptoms',
    'notes',
    'follow_up_required',
    'follow_up_date',
)


def _emergency_columns():
    from models.emergency import EmergencyCase

    return set(EmergencyCase.__table__.columns.keys())


class TestPhantomColumnRegression:
    def test_real_treatment_columns_exist_on_model(self):
        cols = _emergency_columns()
        missing = [c for c in REAL_TREATMENT_COLUMNS if c not in cols]
        assert not missing, f'Missing real columns: {missing}'

    def test_phantom_columns_absent_from_model(self):
        cols = _emergency_columns()
        present = [c for c in PHANTOM_COLUMNS if c in cols]
        assert not present, f'Phantom columns leaked onto model: {present}'

    def test_route_written_attrs_are_all_real_columns(self):
        cols = _emergency_columns()
        written_by_routes = {
            'chief_complaint',
            'diagnosis',
            *REAL_TREATMENT_COLUMNS,
            'triage_notes',
            'vital_signs',
            'severity',
            'status',
            'completed_at',
            'created_at',
            'patient_id',
            'lab_request_id',
            'radiology_request_id',
        }
        unknown = [c for c in sorted(written_by_routes) if c not in cols]
        assert not unknown, f'Routes write non-column attrs: {unknown}'


@pytest.fixture()
def _emg_env(client, db, test_tenant):
    """Patient + medication + emergency case (+ optional visit), logged-in emergency staff."""
    from models.emergency import EmergencyCase
    from models.medication import Medication
    from models.patient import Patient
    from models.visit import Visit
    from tests.tenant_context import ensure_test_user, login_test_client

    tag = uuid.uuid4().hex[:6]
    patient = Patient(
        tenant_id=test_tenant.id,
        first_name='EmgHard',
        last_name=tag,
        gender='M',
        phone='050' + str(uuid.uuid4().int % 10**7),
    )
    _db.session.add(patient)
    _db.session.flush()

    med = Medication(
        tenant_id=test_tenant.id,
        trade_name=f'EMed-{tag}',
        scientific_name=f'ES-{tag}',
        dosage_form='tablet',
        strength='500mg',
        price=5,
        stock_quantity=50,
        minimum_stock=5,
        category='general',
        is_active=True,
    )
    _db.session.add(med)

    visit = Visit(
        tenant_id=test_tenant.id,
        patient_id=patient.id,
        visit_type='EMERGENCY',
        is_emergency=True,
        status='IN_PROGRESS',
    )
    _db.session.add(visit)
    _db.session.flush()

    case = EmergencyCase(
        tenant_id=test_tenant.id,
        patient_id=patient.id,
        visit_id=visit.id,
        case_number=f'EC-H-{tag}',
        chief_complaint='ألم حاد',
        severity='HIGH',
    )
    walkin_case = EmergencyCase(
        tenant_id=test_tenant.id,
        patient_id=patient.id,
        visit_id=None,
        case_number=f'EC-W-{tag}',
        chief_complaint='وصول مباشر',
        severity='MODERATE',
    )
    _db.session.add_all([case, walkin_case])
    _db.session.commit()

    user = ensure_test_user(db, test_tenant, username=f'emgh_{tag}', role='emergency')
    login_test_client(client, user, test_tenant)

    return {
        'tag': tag,
        'patient_id': patient.id,
        'visit_id': visit.id,
        'case_id': case.id,
        'walkin_case_id': walkin_case.id,
        'med_name': med.trade_name,
        'user_id': user.id,
        'tenant_id': test_tenant.id,
    }


def _prescription_count():
    from models.medication import Prescription

    return _db.session.execute(select(func.count()).select_from(Prescription)).scalar()


def _flashes(client):
    with client.session_transaction() as sess:
        return list(sess.get('_flashes') or [])


class TestPrescriptionPersistence:
    def test_post_creates_real_prescription_row(self, client, _emg_env):
        from models.medication import Prescription

        before = _prescription_count()
        resp = client.post(
            f'/emergency/prescription/{_emg_env["case_id"]}',
            data={
                'medications[]': [_emg_env['med_name']],
                'dosages[]': ['500mg'],
                'frequencies[]': ['مرتين يومياً'],
                'durations[]': ['5'],
                'instructions[]': ['بعد الأكل'],
            },
        )
        assert resp.status_code == 302
        after = _prescription_count()
        assert after == before + 1

        rx = (
            _db.session.execute(select(Prescription).order_by(Prescription.id.desc()))
            .scalars()
            .first()
        )
        assert rx is not None
        assert rx.patient_id == _emg_env['patient_id']
        assert rx.visit_id == _emg_env['visit_id']
        assert rx.items.count() == 1
        assert any('تم إنشاء الوصفة بنجاح' in msg for _, msg in _flashes(client))

    def test_walkin_post_persists_without_visit(self, client, _emg_env):
        from models.medication import Prescription

        before = _prescription_count()
        resp = client.post(
            f'/emergency/prescription/{_emg_env["walkin_case_id"]}',
            data={
                'medications[]': [_emg_env['med_name']],
                'dosages[]': ['1 قرص'],
                'frequencies[]': ['مرة يومياً'],
                'durations[]': ['3'],
            },
        )
        assert resp.status_code == 302
        assert _prescription_count() == before + 1
        rx = (
            _db.session.execute(
                select(Prescription)
                .filter_by(patient_id=_emg_env['patient_id'])
                .order_by(Prescription.id.desc())
            )
            .scalars()
            .first()
        )
        assert rx.visit_id is None

    def test_post_with_unknown_medication_creates_nothing(self, client, _emg_env):
        before = _prescription_count()
        resp = client.post(
            f'/emergency/prescription/{_emg_env["case_id"]}',
            data={'medications[]': ['دواء-غير-موجود-نهائياً'], 'dosages[]': ['1']},
        )
        assert resp.status_code == 302
        assert _prescription_count() == before
        flashes = _flashes(client)
        assert any('يرجى إضافة دواء' in msg for _, msg in flashes)
        assert not any('بنجاح' in msg for _, msg in flashes)


class TestTreatmentPersistence:
    def test_treatment_post_persists_all_fields(self, client, _emg_env):
        from models.emergency import EmergencyCase

        resp = client.post(
            f'/emergency/treatment/{_emg_env["case_id"]}',
            data={
                'chief_complaint': 'ألم صدري',
                'diagnosis': 'ذبحة صدرية',
                'treatment_given': 'أكسجين ومسكنات وريدية',
                'medications': 'أسبرين، مورفين',
                'procedures': 'تخطيط قلب، تركيب محاليل',
            },
        )
        assert resp.status_code == 302
        _db.session.expire_all()
        case = _db.session.get(EmergencyCase, _emg_env['case_id'])
        assert case.treatment_given == 'أكسجين ومسكنات وريدية'
        assert case.medications_text == 'أسبرين، مورفين'
        assert case.procedures_text == 'تخطيط قلب، تركيب محاليل'
        assert case.diagnosis == 'ذبحة صدرية'
        assert case.treated_by_id == _emg_env['user_id']
        assert case.treatment_completed_at is not None

    def test_start_and_end_treatment_persist_audit_columns(self, client, _emg_env):
        from models.emergency import EmergencyCase

        resp_start = client.post(f'/emergency/start-treatment/{_emg_env["walkin_case_id"]}')
        assert resp_start.status_code == 302
        resp_end = client.post(f'/emergency/end-treatment/{_emg_env["walkin_case_id"]}')
        assert resp_end.status_code == 302

        _db.session.expire_all()
        case = _db.session.get(EmergencyCase, _emg_env['walkin_case_id'])
        assert case.treatment_started_at is not None
        assert case.treated_by_id == _emg_env['user_id']
        assert case.completed_at is not None
        assert case.completed_by_id == _emg_env['user_id']

    def test_edit_maps_notes_and_treatment_to_real_columns(self, client, _emg_env):
        from models.emergency import EmergencyCase

        resp = client.post(
            f'/emergency/cases/{_emg_env["case_id"]}/edit',
            data={
                'chief_complaint': '',
                'symptoms': 'دوخة شديدة',
                'initial_assessment': 'ارتفاع ضغط',
                'treatment_given': 'خافض ضغط وريدي',
                'notes': 'ملاحظات التحرير',
                'vital_signs_bp_systolic': '150',
                'vital_signs_bp_diastolic': '95',
            },
        )
        assert resp.status_code == 302
        _db.session.expire_all()
        case = _db.session.get(EmergencyCase, _emg_env['case_id'])
        assert case.chief_complaint == 'دوخة شديدة'
        assert case.diagnosis == 'ارتفاع ضغط'
        assert case.treatment_given == 'خافض ضغط وريدي'
        assert case.triage_notes == 'ملاحظات التحرير'
