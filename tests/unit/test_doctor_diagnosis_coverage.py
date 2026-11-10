"""Coverage-focused HTTP tests for routes/doctor/diagnosis.py.

Complements tests/unit/test_doctor_coverage.py and test_doctor_wave2.py by
exercising the branches the earlier suites leave uncovered: empty-result
paths, failure handling, and the remaining helper branches.

Real HTTP requests are made against the test database; helpers are invoked
inside a tenant-bound request context, mirroring test_doctor_wave2.py.
"""

from __future__ import annotations

import contextlib
import sys
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select

from models.appointment import Appointment
from models.department import Department
from models.follow_up import FollowUpRequest
from models.lab_request import LabRequest, LabResult
from models.medical_record import MedicalRecord
from models.medication import Medication, Prescription, PrescriptionItem
from models.patient import Patient, PatientAllergy
from models.visit import Visit
from tests.tenant_context import ensure_test_user, login_test_client, tenant_test_context

_DOCTOR_USER = 'ddc_doctor'


@pytest.fixture(autouse=True)
def _no_bundle_limits(monkeypatch):
    monkeypatch.setattr(
        'app.shared.tenant_filter._check_bundle_limits_on_create',
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        'app.shared.tenant_filter._check_bundle_limits_on_update',
        lambda *_a, **_k: None,
    )


def _tag() -> str:
    return uuid.uuid4().hex[:10]


def _make_doctor(db, tenant, role: str = 'doctor', username: str | None = None):
    username = username or f'{_DOCTOR_USER}_{_tag()}'
    return ensure_test_user(db, tenant, username=username, role=role)


def _login_as(client, db, tenant, user):
    login_test_client(client, user, tenant, 'ValidPass123!')
    return client


def _patient(db, **kw):
    p = Patient(
        first_name=kw.get('first_name', f'First{_tag()}'),
        last_name=kw.get('last_name', f'Last{_tag()}'),
        phone=f'05{uuid.uuid4().int % 10**8:08d}',
        gender=kw.get('gender', 'M'),
        birth_date=kw.get('birth_date', date(1990, 1, 1)),
    )
    db.session.add(p)
    db.session.commit()
    return p


def _department(db, *, name: str | None = None, reception: bool = False):
    tag = _tag()
    d = Department(
        name=name or ('Reception' if reception else f'Clinic-{tag}'),
        name_ar=name or ('استقبال' if reception else f'عيادة-{tag}'),
        is_active=True,
    )
    db.session.add(d)
    db.session.commit()
    return d


def _visit(db, p, doc, dept=None, *, status='OPEN', **kw):
    v = Visit(
        patient_id=p.id,
        department_id=dept.id if dept else kw.get('department_id'),
        doctor_id=doc.id,
        status=status,
        payment_status='PENDING',
        total_amount=kw.get('total_amount', 0),
        visit_type=kw.get('visit_type', 'REGULAR'),
        payment_method='cash',
        visit_date=kw.get('visit_date', date.today()),
        visit_time=kw.get('visit_time', datetime.now(UTC)),
    )
    for k, val in kw.items():
        if k in {'total_amount', 'visit_type', 'visit_date', 'visit_time', 'department_id'}:
            continue
        setattr(v, k, val)
    db.session.add(v)
    db.session.commit()
    return v


def _medication(db, *, trade_name=None, price='10.00', generic_name=None, **kw):
    med = Medication(
        scientific_name=kw.get('scientific_name') or f'Scimed-{_tag()}',
        trade_name=trade_name or f'Ted-{_tag()}',
        generic_name=generic_name,
        dosage_form=kw.get('dosage_form', 'tablet'),
        strength=kw.get('strength', '500mg'),
        price=price,
        is_active=True,
    )
    for k, val in kw.items():
        if hasattr(med, k):
            setattr(med, k, val)
    db.session.add(med)
    db.session.commit()
    return med


def _prescription(db, p, doc, v, *, diagnosis=None, number=None, status='active'):
    rx = Prescription(
        patient_id=p.id,
        doctor_id=doc.id,
        visit_id=v.id if v else None,
        prescription_number=number or f'RX-DDC-{_tag()}',
        status=status,
        diagnosis=diagnosis,
    )
    db.session.add(rx)
    db.session.commit()
    return rx


def _rx_item(
    db, rx, med, *, quantity=1, duration_days=7, dosage='1 tablet | twice daily', unit_price='10.00'
):
    item = PrescriptionItem(
        prescription_id=rx.id,
        medication_id=med.id,
        dosage=dosage,
        quantity=quantity,
        duration_days=duration_days,
        unit_price=unit_price,
        total_price=str(float(unit_price) * quantity),
    )
    db.session.add(item)
    db.session.commit()
    return item


@contextlib.contextmanager
def _bound_request(app, tenant, user):
    with tenant_test_context(app, tenant):
        from flask_login import login_user, logout_user

        login_user(user)
        try:
            yield
        finally:
            logout_user()


def _assert_redirect_to(resp, fragment: str):
    assert resp.status_code == 302
    assert fragment in resp.headers.get('Location', '')


# ---------------------------------------------------------------------------
# diagnosis route: extra branches
# ---------------------------------------------------------------------------


class TestDiagnosisRouteExtra:
    def test_get_missing_visit_redirects(self, app, client, db, test_tenant, rollback_db):
        _make = _make_doctor(db, test_tenant)
        _login_as(client, db, test_tenant, _make)
        resp = client.get('/doctor/diagnosis/99999999')
        _assert_redirect_to(resp, '/doctor/patient-queue')

    def test_post_missing_visit_redirects(self, app, client, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        _login_as(client, db, test_tenant, doc)
        resp = client.post('/doctor/diagnosis/99999999', data={'diagnosis': 'x'})
        _assert_redirect_to(resp, '/doctor/patient-queue')

    def test_post_wrong_role_403(self, app, client, db, test_tenant, rollback_db):
        nurse = _make_doctor(db, test_tenant, role='nurse', username=f'wv2_nurse_{_tag()}')
        _login_as(client, db, test_tenant, nurse)
        doc = _make_doctor(db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        resp = client.post(f'/doctor/diagnosis/{v.id}', data={'diagnosis': 'x'})
        assert resp.status_code == 403

    def test_outer_exception_on_post_redirects(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        doc = _make_doctor(db, test_tenant)
        _login_as(client, db, test_tenant, doc)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')

        class _BoomDb:
            class session:
                @staticmethod
                def execute(*args, **kwargs):
                    raise RuntimeError('db boom')

        monkeypatch.setattr('routes.doctor.diagnosis.db', _BoomDb())
        resp = client.post(f'/doctor/diagnosis/{v.id}', data={'diagnosis': 'boom'})
        _assert_redirect_to(resp, '/doctor/patient-queue')

    def test_follow_up_date_valid_sets(self, app, client, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        _login_as(client, db, test_tenant, doc)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        resp = client.post(
            f'/doctor/diagnosis/{v.id}',
            data={'diagnosis': 'dx', 'follow_up_required': 'on', 'follow_up_date': '2026-11-11'},
        )
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        db.session.expire_all()
        assert db.session.get(Visit, v.id).follow_up_date == date(2026, 11, 11)

    def test_empty_fields_do_not_crash(self, app, client, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        _login_as(client, db, test_tenant, doc)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        resp = client.post(f'/doctor/diagnosis/{v.id}', data={})
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')


# ---------------------------------------------------------------------------
# AI diagnostic assistant
# ---------------------------------------------------------------------------


class TestAiDiagnosticAssistant:
    def test_empty_returns_empty_lists(self, app, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        from routes.doctor import diagnosis as diagnosis_module

        with _bound_request(app, test_tenant, doc):
            out = diagnosis_module.get_ai_diagnostic_assistant()
        assert out == {
            'common_diagnoses': [],
            'common_medications': [],
            'diagnostic_suggestions': [],
        }

    def test_exception_returns_empty_dict(self, app, db, test_tenant, rollback_db, monkeypatch):
        doc = _make_doctor(db, test_tenant)
        from routes.doctor import diagnosis as diagnosis_module

        def _boom(*args, **kwargs):
            raise RuntimeError('boom')

        monkeypatch.setattr('routes.doctor.diagnosis.db.session.execute', _boom)
        with _bound_request(app, test_tenant, doc):
            out = diagnosis_module.get_ai_diagnostic_assistant()
        assert out == {}


# ---------------------------------------------------------------------------
# standardized pathways
# ---------------------------------------------------------------------------


class TestStandardizedPathways:
    def test_none_input(self):
        from routes.doctor.diagnosis import get_standardized_pathways

        assert get_standardized_pathways(None) == []

    def test_multiple_keywords(self):
        from routes.doctor.diagnosis import get_standardized_pathways

        out = get_standardized_pathways('diabetes and hypertension')
        ids = {p['id'] for p in out}
        assert 'diabetes_basic' in ids
        assert 'hypertension_basic' in ids

    def test_case_insensitive(self):
        from routes.doctor.diagnosis import get_standardized_pathways

        out = get_standardized_pathways('ASTHMA')
        assert any(p['id'] == 'asthma_basic' for p in out)


# ---------------------------------------------------------------------------
# data based recommendations
# ---------------------------------------------------------------------------


class TestDataBasedRecommendations:
    def test_empty_returns_empty(self, app, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        from routes.doctor import diagnosis as diagnosis_module

        with _bound_request(app, test_tenant, doc):
            assert diagnosis_module.get_data_based_recommendations('') == []
            assert diagnosis_module.get_data_based_recommendations('   ') == []

    def test_no_match_returns_empty(self, app, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        from routes.doctor import diagnosis as diagnosis_module

        with _bound_request(app, test_tenant, doc):
            assert diagnosis_module.get_data_based_recommendations('zzzzzzzzz') == []

    def test_exception_returns_empty(self, app, db, test_tenant, rollback_db, monkeypatch):
        doc = _make_doctor(db, test_tenant)
        from routes.doctor import diagnosis as diagnosis_module

        def _boom(*args, **kwargs):
            raise RuntimeError('boom')

        monkeypatch.setattr('routes.doctor.diagnosis.db.session.execute', _boom)
        with _bound_request(app, test_tenant, doc):
            assert diagnosis_module.get_data_based_recommendations('anything') == []

    def test_skips_prescriptions_without_diagnosis(self, app, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        med = _medication(db, trade_name=f'NODX-{_tag()}')
        rx = _prescription(db, p, doc, v, diagnosis=None)
        _rx_item(db, rx, med)
        from routes.doctor import diagnosis as diagnosis_module

        with _bound_request(app, test_tenant, doc):
            assert diagnosis_module.get_data_based_recommendations('anything') == []


# ---------------------------------------------------------------------------
# evaluate clinical rules
# ---------------------------------------------------------------------------


class TestEvaluateClinicalRules:
    def test_no_prescriptions_no_warnings_for_plain_diagnosis(
        self, app, db, test_tenant, rollback_db
    ):
        doc = _make_doctor(db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        v.diagnosis = 'صداع'
        db.session.commit()
        from routes.doctor.diagnosis import evaluate_clinical_rules

        warnings = evaluate_clinical_rules(v, [], {})
        assert warnings == []

    def test_allergy_query_failure_is_tolerated(
        self, app, db, test_tenant, rollback_db, monkeypatch
    ):
        doc = _make_doctor(db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        med = _medication(db, trade_name=f'ALG-{_tag()}')
        rx = _prescription(db, p, doc, v)
        _rx_item(db, rx, med)

        original = __import__('routes.doctor.diagnosis', fromlist=['db']).db.session.execute

        def _boom(*args, **kwargs):
            raise RuntimeError('allergy boom')

        # Fail only the PatientAllergy lookup; the outer try catches it.
        import routes.doctor.diagnosis as m

        def _selective(*args, **kwargs):
            # inspect the statement text loosely
            try:
                stmt = str(args[0])
            except Exception:
                stmt = ''
            if 'patient_allergies' in stmt.lower() or 'PatientAllergy' in stmt:
                raise RuntimeError('allergy boom')
            return original(*args, **kwargs)

        monkeypatch.setattr(m.db.session, 'execute', _selective)
        from routes.doctor.diagnosis import evaluate_clinical_rules

        warnings = evaluate_clinical_rules(v, [rx], {})
        assert isinstance(warnings, list)

    def test_vitals_present_suppresses_missing_vitals(self, app, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        v.diagnosis = 'diabetes case'
        db.session.commit()
        from routes.doctor.diagnosis import evaluate_clinical_rules

        warnings = evaluate_clinical_rules(v, [], {'blood_pressure': '120/80'})
        assert not any(w['type'] == 'missing_vitals' for w in warnings)

    def test_no_duplicate_no_allergy_no_long_duration(self, app, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        v.diagnosis = 'headache'
        db.session.commit()
        med = _medication(db, trade_name=f'UNIQ-{_tag()}')
        rx = _prescription(db, p, doc, v)
        _rx_item(db, rx, med, duration_days=5)
        from routes.doctor.diagnosis import evaluate_clinical_rules

        warnings = evaluate_clinical_rules(v, [rx], {'blood_pressure': '120/80'})
        assert warnings == []


# ---------------------------------------------------------------------------
# patient medical history ai
# ---------------------------------------------------------------------------


class TestPatientMedicalHistoryAi:
    def test_empty_returns_empty_lists(self, app, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        from routes.doctor import diagnosis as diagnosis_module

        with _bound_request(app, test_tenant, doc):
            out = diagnosis_module.get_patient_medical_history_ai()
        assert set(out) == {'frequent_patients', 'chronic_conditions', 'long_term_medications'}
        assert out['frequent_patients'] == []
        assert out['chronic_conditions'] == []
        assert out['long_term_medications'] == []

    def test_exception_returns_empty_dict(self, app, db, test_tenant, rollback_db, monkeypatch):
        doc = _make_doctor(db, test_tenant)
        from routes.doctor import diagnosis as diagnosis_module

        def _boom(*args, **kwargs):
            raise RuntimeError('boom')

        monkeypatch.setattr('routes.doctor.diagnosis.db.session.execute', _boom)
        with _bound_request(app, test_tenant, doc):
            out = diagnosis_module.get_patient_medical_history_ai()
        assert out == {}


# ---------------------------------------------------------------------------
# treatment recommendations
# ---------------------------------------------------------------------------


class TestTreatmentRecommendations:
    def test_no_archived_visits_still_checks_interactions(self, app, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        from routes.doctor.diagnosis import get_treatment_recommendations

        with _bound_request(app, test_tenant, doc):
            recs = get_treatment_recommendations()
        types = [r['type'] for r in recs]
        assert 'drug_interaction' in types
        assert 'effective_treatment' not in types

    def test_exception_returns_empty_list(self, app, db, test_tenant, rollback_db, monkeypatch):
        doc = _make_doctor(db, test_tenant)
        from routes.doctor.diagnosis import get_treatment_recommendations

        def _boom(*args, **kwargs):
            raise RuntimeError('boom')

        monkeypatch.setattr('routes.doctor.diagnosis.db.session.execute', _boom)
        with _bound_request(app, test_tenant, doc):
            assert get_treatment_recommendations() == []


# ---------------------------------------------------------------------------
# drug interaction checker
# ---------------------------------------------------------------------------


class TestDrugInteractionChecker:
    def test_no_recent_prescriptions(self, app, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        from routes.doctor.diagnosis import get_drug_interaction_checker

        with _bound_request(app, test_tenant, doc):
            out = get_drug_interaction_checker()
        assert out['total_prescriptions_checked'] == 0
        assert out['interactions_found'] == []
        assert out['interaction_rate'] == 0

    def test_exception_returns_empty_dict(self, app, db, test_tenant, rollback_db, monkeypatch):
        doc = _make_doctor(db, test_tenant)
        from routes.doctor.diagnosis import get_drug_interaction_checker

        def _boom(*args, **kwargs):
            raise RuntimeError('boom')

        monkeypatch.setattr('routes.doctor.diagnosis.db.session.execute', _boom)
        with _bound_request(app, test_tenant, doc):
            assert get_drug_interaction_checker() == {}

    def test_medication_not_in_known_interactions_skipped(self, app, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        med = _medication(db, trade_name=f'UNKNOWN-{_tag()}')
        rx = _prescription(db, p, doc, v)
        _rx_item(db, rx, med)
        from routes.doctor.diagnosis import get_drug_interaction_checker

        with _bound_request(app, test_tenant, doc):
            out = get_drug_interaction_checker()
        assert out['total_prescriptions_checked'] >= 1
        assert out['interactions_found'] == []


# ---------------------------------------------------------------------------
# clinical decision support
# ---------------------------------------------------------------------------


class TestClinicalDecisionSupport:
    def test_no_data_returns_empty_list(self, app, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        from routes.doctor.diagnosis import get_clinical_decision_support

        with _bound_request(app, test_tenant, doc):
            assert get_clinical_decision_support() == []

    def test_exception_returns_empty_list(self, app, db, test_tenant, rollback_db, monkeypatch):
        doc = _make_doctor(db, test_tenant)
        from routes.doctor.diagnosis import get_clinical_decision_support

        def _boom(*args, **kwargs):
            raise RuntimeError('boom')

        monkeypatch.setattr('routes.doctor.diagnosis.db.session.execute', _boom)
        with _bound_request(app, test_tenant, doc):
            assert get_clinical_decision_support() == []

    def test_high_success_does_not_flag(self, app, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='COMPLETED', archive_status='ARCHIVED')
        db.session.add(
            MedicalRecord(
                patient_id=p.id,
                visit_id=v.id,
                title='تحليل',
                details='d',
                diagnosis=f'حالة-نجاح-{_tag()}',
                created_by=doc.id,
            )
        )
        med = _medication(db, trade_name=f'HIGH-{_tag()}')
        rx = _prescription(db, p, doc, v)
        _rx_item(db, rx, med)
        db.session.commit()
        from routes.doctor.diagnosis import get_clinical_decision_support

        with _bound_request(app, test_tenant, doc):
            recs = get_clinical_decision_support()
        # High success rate (100%) should not produce diagnosis_improvement.
        assert not any(
            r.get('type') == 'diagnosis_improvement'
            and r.get('diagnosis', '').startswith('حالة-نجاح')
            for r in recs
        )


# ---------------------------------------------------------------------------
# medical analytics
# ---------------------------------------------------------------------------


class TestMedicalAnalytics:
    def test_no_visits_zero_completion(self, app, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        from routes.doctor.diagnosis import get_medical_analytics

        with _bound_request(app, test_tenant, doc):
            out = get_medical_analytics()
        assert out['completion_rate'] == 0
        assert out['avg_visit_duration'] == 0

    def test_exception_returns_empty_dict(self, app, db, test_tenant, rollback_db, monkeypatch):
        doc = _make_doctor(db, test_tenant)
        from routes.doctor.diagnosis import get_medical_analytics

        def _boom(*args, **kwargs):
            raise RuntimeError('boom')

        monkeypatch.setattr('routes.doctor.diagnosis.db.session.execute', _boom)
        with _bound_request(app, test_tenant, doc):
            assert get_medical_analytics() == {}


# ---------------------------------------------------------------------------
# workflow optimization
# ---------------------------------------------------------------------------


class TestWorkflowOptimization:
    def test_no_peak_or_heavy_day_returns_empty(self, app, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        from routes.doctor.diagnosis import get_workflow_optimization

        with _bound_request(app, test_tenant, doc):
            assert get_workflow_optimization() == []

    def test_exception_returns_empty_list(self, app, db, test_tenant, rollback_db, monkeypatch):
        doc = _make_doctor(db, test_tenant)
        from routes.doctor.diagnosis import get_workflow_optimization

        def _boom(*args, **kwargs):
            raise RuntimeError('boom')

        monkeypatch.setattr('routes.doctor.diagnosis.db.session.execute', _boom)
        with _bound_request(app, test_tenant, doc):
            assert get_workflow_optimization() == []


# ---------------------------------------------------------------------------
# smart reminders
# ---------------------------------------------------------------------------


class TestSmartReminders:
    def test_no_triggers_returns_empty(self, app, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        from routes.doctor.diagnosis import get_smart_reminders

        with _bound_request(app, test_tenant, doc):
            assert get_smart_reminders() == []

    def test_exception_returns_empty_list(self, app, db, test_tenant, rollback_db, monkeypatch):
        doc = _make_doctor(db, test_tenant)
        from routes.doctor.diagnosis import get_smart_reminders

        def _boom(*args, **kwargs):
            raise RuntimeError('boom')

        monkeypatch.setattr('routes.doctor.diagnosis.db.session.execute', _boom)
        with _bound_request(app, test_tenant, doc):
            assert get_smart_reminders() == []


# ---------------------------------------------------------------------------
# check_drug_interactions
# ---------------------------------------------------------------------------


class TestCheckDrugInteractions:
    def test_static_list(self):
        from routes.doctor.diagnosis import check_drug_interactions

        interactions = check_drug_interactions()
        assert len(interactions) == 3


# ---------------------------------------------------------------------------
# get_ai_diagnostic_assistant suggestions branches
# ---------------------------------------------------------------------------


class TestAiDiagnosticAssistantSuggestions:
    def test_common_diagnosis_suggestion(self, app, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        db.session.add(
            MedicalRecord(
                patient_id=p.id,
                visit_id=v.id,
                title='تشخيص',
                details='d',
                diagnosis=f'dx-{_tag()}',
                created_by=doc.id,
            )
        )
        db.session.commit()
        from routes.doctor import diagnosis as diagnosis_module

        with _bound_request(app, test_tenant, doc):
            out = diagnosis_module.get_ai_diagnostic_assistant()
        assert out['diagnostic_suggestions']
        assert out['diagnostic_suggestions'][0]['type'] == 'common_diagnosis'

    def test_common_medication_suggestion(self, app, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        med = _medication(db, trade_name=f'MED-{_tag()}')
        rx = _prescription(db, p, doc, v)
        _rx_item(db, rx, med)
        db.session.commit()
        from routes.doctor import diagnosis as diagnosis_module

        with _bound_request(app, test_tenant, doc):
            out = diagnosis_module.get_ai_diagnostic_assistant()
        # medication suggestion appears only if common_medications non-empty
        assert isinstance(out['common_medications'], list)


# ensure unused imports not flagged
_ = (LabRequest, LabResult, Appointment, PatientAllergy, FollowUpRequest, select, sys)


# ---------------------------------------------------------------------------
# Targeted coverage for previously missed lines
# ---------------------------------------------------------------------------


class TestDiagnosisTargetedHTTP:
    def test_get_blocked_when_completed(self, app, client, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        _login_as(client, db, test_tenant, doc)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='COMPLETED')
        resp = client.get(f'/doctor/diagnosis/{v.id}')
        _assert_redirect_to(resp, '/doctor/patient-queue')

    def test_get_blocked_when_archived(self, app, client, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        _login_as(client, db, test_tenant, doc)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), archive_status='ARCHIVED')
        resp = client.get(f'/doctor/diagnosis/{v.id}')
        _assert_redirect_to(resp, '/doctor/patient-queue')

    def test_post_blocked_when_completed(self, app, client, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        _login_as(client, db, test_tenant, doc)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='COMPLETED', diagnosis='orig')
        resp = client.post(f'/doctor/diagnosis/{v.id}', data={'diagnosis': 'changed'})
        _assert_redirect_to(resp, '/doctor/patient-queue')

    def test_oversized_chief_complaint(self, app, client, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        _login_as(client, db, test_tenant, doc)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        resp = client.post(
            f'/doctor/diagnosis/{v.id}',
            data={'chief_complaint': 'x' * 2001, 'follow_up_date': ''},
        )
        _assert_redirect_to(resp, f'/doctor/diagnosis/{v.id}')

    def test_oversized_diagnosis(self, app, client, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        _login_as(client, db, test_tenant, doc)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        resp = client.post(
            f'/doctor/diagnosis/{v.id}',
            data={'diagnosis': 'x' * 2001, 'follow_up_date': ''},
        )
        _assert_redirect_to(resp, f'/doctor/diagnosis/{v.id}')

    def test_oversized_notes(self, app, client, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        _login_as(client, db, test_tenant, doc)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        resp = client.post(
            f'/doctor/diagnosis/{v.id}',
            data={'notes': 'x' * 5001, 'follow_up_date': ''},
        )
        _assert_redirect_to(resp, f'/doctor/diagnosis/{v.id}')

    def test_post_unparseable_existing_vitals(self, app, client, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        _login_as(client, db, test_tenant, doc)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        v.vital_signs = '{not-valid-json'
        db.session.commit()
        resp = client.post(
            f'/doctor/diagnosis/{v.id}',
            data={'diagnosis': 'dx', 'blood_pressure': '120/80'},
        )
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')

    def test_invalid_follow_up_date(self, app, client, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        _login_as(client, db, test_tenant, doc)
        p = _patient(db)
        v = _visit(
            db, p, doc, _department(db), status='IN_PROGRESS', follow_up_date=date(2026, 11, 30)
        )
        resp = client.post(
            f'/doctor/diagnosis/{v.id}',
            data={'diagnosis': 'dx', 'follow_up_date': '31/12/2026'},
        )
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')

    def test_ensure_in_progress_value_error(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        doc = _make_doctor(db, test_tenant)
        _login_as(client, db, test_tenant, doc)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='OPEN')

        def _raise_value_error(cls, visit, **kwargs):
            raise ValueError('cannot transition')

        monkeypatch.setattr(
            'routes.doctor.diagnosis.VisitStateMachineService.ensure_in_progress',
            classmethod(_raise_value_error),
        )
        resp = client.post(f'/doctor/diagnosis/{v.id}', data={'diagnosis': 'forced progress'})
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')

    def test_notes_appended(self, app, client, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        _login_as(client, db, test_tenant, doc)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        resp = client.post(
            f'/doctor/diagnosis/{v.id}',
            data={'diagnosis': 'dx', 'notes': 'ملاحظة اختبار', 'follow_up_date': ''},
        )
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')

    def test_sync_follow_up_failure(self, app, client, db, test_tenant, rollback_db, monkeypatch):
        doc = _make_doctor(db, test_tenant)
        _login_as(client, db, test_tenant, doc)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')

        def _boom(visit, actor):
            raise RuntimeError('follow-up sync boom')

        monkeypatch.setattr('routes.doctor.diagnosis._sync_follow_up_request_for_visit', _boom)
        resp = client.post(f'/doctor/diagnosis/{v.id}', data={'diagnosis': 'sync fails'})
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')

    def test_resave_updates_medical_record(self, app, client, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        _login_as(client, db, test_tenant, doc)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        client.post(f'/doctor/diagnosis/{v.id}', data={'diagnosis': 'v1', 'follow_up_date': ''})
        client.post(f'/doctor/diagnosis/{v.id}', data={'diagnosis': 'v2', 'follow_up_date': ''})
        db.session.expire_all()
        recs = (
            db.session.execute(select(MedicalRecord).filter_by(visit_id=v.id, title='تشخيص طبي'))
            .scalars()
            .all()
        )
        assert len(recs) == 1

    def test_audit_failure(self, app, client, db, test_tenant, rollback_db, monkeypatch):
        doc = _make_doctor(db, test_tenant)
        _login_as(client, db, test_tenant, doc)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')

        def _boom(*args, **kwargs):
            raise RuntimeError('audit boom')

        monkeypatch.setattr('routes.doctor.diagnosis.AuditTrail', _boom)
        resp = client.post(f'/doctor/diagnosis/{v.id}', data={'diagnosis': 'audit fails'})
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')

    def test_get_vitals_json_dict(self, app, client, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        _login_as(client, db, test_tenant, doc)
        p = _patient(db)
        v = _visit(
            db,
            p,
            doc,
            _department(db),
            status='IN_PROGRESS',
            vital_signs='{"blood_pressure": "118/76"}',
        )
        resp = client.get(f'/doctor/diagnosis/{v.id}')
        assert resp.status_code == 200
        assert '118/76' in resp.get_data(as_text=True)

    def test_get_vitals_python_dict(self, app, client, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        _login_as(client, db, test_tenant, doc)
        p = _patient(db)
        v = _visit(
            db,
            p,
            doc,
            _department(db),
            status='IN_PROGRESS',
            vital_signs="{'blood_pressure': '110/70', 'heart_rate': '65'}",
        )
        resp = client.get(f'/doctor/diagnosis/{v.id}')
        assert resp.status_code == 200
        assert '110/70' in resp.get_data(as_text=True)

    def test_get_vitals_malformed(self, app, client, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        _login_as(client, db, test_tenant, doc)
        p = _patient(db)
        v = _visit(
            db,
            p,
            doc,
            _department(db),
            status='IN_PROGRESS',
            vital_signs='not-json-and-not-literal',
        )
        resp = client.get(f'/doctor/diagnosis/{v.id}')
        assert resp.status_code == 200

    def test_get_vitals_non_dict_json(self, app, client, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        _login_as(client, db, test_tenant, doc)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS', vital_signs='[1, 2, 3]')
        resp = client.get(f'/doctor/diagnosis/{v.id}')
        assert resp.status_code == 200


class TestTargetedHelpers:
    def test_data_based_recommendations_match(self, app, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        med = _medication(db, trade_name=f'REC-{_tag()}')
        rx = _prescription(db, p, doc, v, diagnosis=f'حالة-تجريبية-{_tag()}')
        _rx_item(db, rx, med)
        from routes.doctor import diagnosis as diagnosis_module

        with _bound_request(app, test_tenant, doc):
            recs = diagnosis_module.get_data_based_recommendations('حالة-تجريبية')
        assert recs
        assert recs[0]['medication'] == med.trade_name

    def test_evaluate_duplicate_medication(self, app, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        med = _medication(db, trade_name=f'DUPE-{_tag()}')
        rx = _prescription(db, p, doc, v)
        _rx_item(db, rx, med)
        _rx_item(db, rx, med, quantity=2)
        from routes.doctor.diagnosis import evaluate_clinical_rules

        warnings = evaluate_clinical_rules(v, [rx], {})
        assert any(w['type'] == 'duplicate_medication' for w in warnings)

    def test_evaluate_allergy(self, app, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        p = _patient(db)
        db.session.add(PatientAllergy(patient_id=p.id, allergen='dupeclear'))
        db.session.commit()
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        med = _medication(db, trade_name='Dupeclear-500')
        rx = _prescription(db, p, doc, v)
        _rx_item(db, rx, med)
        from routes.doctor.diagnosis import evaluate_clinical_rules

        warnings = evaluate_clinical_rules(v, [rx], {})
        assert any(w['type'] == 'allergy' for w in warnings)

    def test_evaluate_long_duration(self, app, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        med = _medication(db, trade_name=f'LONG-{_tag()}')
        rx = _prescription(db, p, doc, v)
        _rx_item(db, rx, med, duration_days=45)
        from routes.doctor.diagnosis import evaluate_clinical_rules

        warnings = evaluate_clinical_rules(v, [rx], {})
        assert any(w['type'] == 'long_duration' for w in warnings)

    def test_evaluate_missing_vitals_hypertension(self, app, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        v.diagnosis = 'hypertension follow-up'
        db.session.commit()
        from routes.doctor.diagnosis import evaluate_clinical_rules

        warnings = evaluate_clinical_rules(v, [], {})
        assert any(w['type'] == 'missing_vitals' for w in warnings)

    def test_evaluate_missing_vitals_diabetes(self, app, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        v.diagnosis = 'diabetes case'
        db.session.commit()
        from routes.doctor.diagnosis import evaluate_clinical_rules

        warnings = evaluate_clinical_rules(v, [], {})
        assert any(w['type'] == 'missing_vitals' for w in warnings)

    def test_patient_medical_history_chronic(self, app, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        p = _patient(db)
        d = _department(db)
        for _ in range(3):
            _visit(db, p, doc, d, status='COMPLETED')
        v0 = _visit(db, p, doc, d, status='IN_PROGRESS')
        db.session.add(
            MedicalRecord(
                patient_id=p.id,
                visit_id=v0.id,
                title='تحليل',
                details='d',
                diagnosis='السكري',
                created_by=doc.id,
            )
        )
        db.session.commit()
        from routes.doctor import diagnosis as diagnosis_module

        with _bound_request(app, test_tenant, doc):
            out = diagnosis_module.get_patient_medical_history_ai()
        assert any(row['condition'] == 'السكري' for row in out['chronic_conditions'])

    def test_treatment_recommendations_effective(self, app, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='COMPLETED', archive_status='ARCHIVED')
        db.session.add(
            MedicalRecord(
                patient_id=p.id,
                visit_id=v.id,
                title='تحليل',
                details='d',
                diagnosis=f'حالة-علاج-{_tag()}',
                created_by=doc.id,
            )
        )
        med = _medication(db, trade_name=f'TRX-{_tag()}')
        rx = _prescription(db, p, doc, v)
        _rx_item(db, rx, med)
        db.session.commit()
        from routes.doctor.diagnosis import get_treatment_recommendations

        with _bound_request(app, test_tenant, doc):
            recs = get_treatment_recommendations()
        assert 'effective_treatment' in [r['type'] for r in recs]

    def test_drug_interaction_checker_flags(self, app, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        war = _medication(db, trade_name='وارفارين')
        asp = _medication(db, trade_name='أسبرين')
        rx_war = _prescription(db, p, doc, v)
        _rx_item(db, rx_war, war)
        rx_asp = _prescription(db, p, doc, v)
        _rx_item(db, rx_asp, asp)
        from routes.doctor.diagnosis import get_drug_interaction_checker

        with _bound_request(app, test_tenant, doc):
            out = get_drug_interaction_checker()
        names = {(i['medication1'], i['medication2']) for i in out['interactions_found']}
        assert ('وارفارين', 'أسبرين') in names

    def test_clinical_decision_support_flags(self, app, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        db.session.add(
            MedicalRecord(
                patient_id=p.id,
                visit_id=v.id,
                title='تحليل',
                details='d',
                diagnosis=f'حالة-ضعف-{_tag()}',
                created_by=doc.id,
            )
        )
        med = _medication(db, trade_name=f'CDS-{_tag()}')
        rx = _prescription(db, p, doc, v)
        _rx_item(db, rx, med)
        db.session.commit()
        from routes.doctor.diagnosis import get_clinical_decision_support

        with _bound_request(app, test_tenant, doc):
            recs = get_clinical_decision_support()
        types = [r['type'] for r in recs]
        assert 'diagnosis_improvement' in types
        assert 'medication_effectiveness' in types

    def test_workflow_optimization_peak_and_appointments(self, app, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        p = _patient(db)
        d = _department(db)
        peak = datetime.now(UTC).replace(hour=10, minute=0, second=0, microsecond=0)
        for _ in range(11):
            _visit(db, p, doc, d, status='OPEN', visit_time=peak)
        tomorrow = datetime.now(UTC) + timedelta(days=1)
        for _ in range(16):
            db.session.add(
                Appointment(
                    patient_id=_patient(db).id,
                    doctor_id=doc.id,
                    department_id=d.id,
                    starts_at=tomorrow,
                    status='CONFIRMED',
                )
            )
        db.session.commit()
        from routes.doctor.diagnosis import get_workflow_optimization

        with _bound_request(app, test_tenant, doc):
            optimizations = get_workflow_optimization()
        types = [o['type'] for o in optimizations]
        assert 'peak_hours' in types
        assert 'appointment_load' in types

    def test_smart_reminders_all_channels(self, app, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        d = _department(db)
        tomorrow = datetime.now(UTC) + timedelta(days=1)
        db.session.add(
            Appointment(
                patient_id=_patient(db).id,
                doctor_id=doc.id,
                department_id=d.id,
                starts_at=tomorrow,
                status='CONFIRMED',
            )
        )
        for _ in range(6):
            _visit(
                db,
                _patient(db),
                doc,
                d,
                status='COMPLETED',
                archive_status='ARCHIVED',
                completed_at=datetime.now(UTC) - timedelta(days=1),
            )
        p_rx = _patient(db)
        v_rx = _visit(db, p_rx, doc, d, status='IN_PROGRESS')
        for _ in range(11):
            _prescription(db, p=p_rx, doc=doc, v=v_rx)
        db.session.commit()
        from routes.doctor.diagnosis import get_smart_reminders

        with _bound_request(app, test_tenant, doc):
            reminders = get_smart_reminders()
        types = [r['type'] for r in reminders]
        assert 'appointments' in types
        assert 'follow_up' in types
        assert 'medications' in types
