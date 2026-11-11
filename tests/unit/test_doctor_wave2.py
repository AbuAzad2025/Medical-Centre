"""Second-wave HTTP-level coverage tests for the doctor blueprint.

Companion to ``tests/unit/test_doctor_coverage.py``. These tests target the
lines that file does not reach:

* the module-level clinical-AI helper functions in ``routes/doctor/diagnosis.py``
* the failure-handling branches in ``routes/doctor/visits.py`` (audit /
  notification / commit failures must not abort the clinical flow)
* the critical-count rendering path of the patient-details page
* the disabled-module redirects (lab / radiology / billing) via the
  ``isolated_tenant`` fixture
* the exception branches of the remaining doctor surfaces

Fixtures (``app``, ``client``, ``db``, ``test_tenant``, ``rollback_db``,
``isolated_tenant``) come from ``tests/conftest.py``. All assertions are made
against real HTTP responses, real database state, or the real helper return
values -- nothing is mocked into looking covered.
"""

from __future__ import annotations

import contextlib
import json
import sys
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import delete, select

from app.shared.enums import LabResultStatus, VisitState
from models.appointment import Appointment
from models.department import Department
from models.follow_up import FollowUpRequest
from models.invoice import Invoice
from models.lab_request import LabRequest, LabResult
from models.medical_record import MedicalRecord
from models.medication import Medication, Prescription, PrescriptionItem
from models.nurse import VitalSigns
from models.patient import Patient, PatientAllergy
from models.queue_management import QueueManagement
from models.radiology_request import RadiologyRequest
from models.radiology_result import RadiologyResult
from models.visit import Visit
from tests.tenant_context import ensure_test_user, login_test_client, tenant_test_context

_DOCTOR_USER = 'wv2_doctor'
_NURSE_USER = 'wv2_nurse'
_MANAGER_USER = 'wv2_manager'


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


def _tick(db, v, dept, *, status='waiting'):
    t = QueueManagement(
        department_id=dept.id,
        patient_id=v.patient_id,
        visit_id=v.id,
        queue_number=f'Q-{_tag()}',
        status=status,
        priority_level='normal',
    )
    db.session.add(t)
    db.session.commit()
    return t


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
        prescription_number=number or f'RX-WV2-{_tag()}',
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


def _doctor_client(client, db, tenant):
    doc = _make_doctor(db, tenant)
    _login_as(client, db, tenant, doc)
    return doc


def _assert_redirect_to(resp, fragment: str):
    assert resp.status_code == 302
    assert fragment in resp.headers.get('Location', '')


def _rx_form(med_ids):
    """Multipart form with one medication row per id (mirrors the browser form)."""
    return {
        'item_medication_id[]': [str(m) for m in med_ids],
        'item_dosage[]': ['5mg' for _ in med_ids],
        'item_frequency[]': ['twice daily' for _ in med_ids],
        'item_duration_days[]': ['7' for _ in med_ids],
        'item_quantity[]': ['2' for _ in med_ids],
        'item_instructions[]': ['' for _ in med_ids],
    }


@contextlib.contextmanager
def _bound_request(app, tenant, user):
    """Push a tenant-bound request context logged in as ``user``."""
    with tenant_test_context(app, tenant):
        from flask_login import login_user, logout_user

        login_user(user)
        try:
            yield
        finally:
            logout_user()


def _disable_module(app, tenant, module_name: str):
    from sqlalchemy import select as _select

    from app.core.module.models import TenantModule
    from app.extensions import db as _db

    with tenant_test_context(app, tenant):
        rows = (
            _db.session.execute(
                _select(TenantModule).filter_by(tenant_id=tenant.id, module_name=module_name)
            )
            .scalars()
            .all()
        )
        for row in rows:
            row.is_active = False
        _db.session.commit()


# ---------------------------------------------------------------------------
# Diagnosis route: gap branches
# ---------------------------------------------------------------------------


class TestDiagnosisPostGaps:
    def test_post_tolerates_unparseable_existing_vital_signs(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        v.vital_signs = '{not-valid-json'
        db.session.commit()

        resp = client.post(
            f'/doctor/diagnosis/{v.id}',
            data={'diagnosis': 'post with corrupt vitals', 'blood_pressure': '120/80'},
        )
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        db.session.expire_all()
        merged = json.loads(db.session.get(Visit, v.id).vital_signs)
        # the corrupt prior value is discarded, the new reading is kept
        assert merged['blood_pressure'] == '120/80'

    def test_post_survives_ensure_in_progress_value_error(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        doc = _doctor_client(client, db, test_tenant)
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
        db.session.expire_all()
        assert db.session.get(Visit, v.id).status == VisitState.IN_PROGRESS.value

    def test_post_survives_follow_up_sync_failure(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')

        def _boom(visit, actor):
            raise RuntimeError('follow-up sync boom')

        monkeypatch.setattr('routes.doctor.diagnosis._sync_follow_up_request_for_visit', _boom)
        resp = client.post(f'/doctor/diagnosis/{v.id}', data={'diagnosis': 'sync fails'})
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        db.session.expire_all()
        assert db.session.get(Visit, v.id).diagnosis == 'sync fails'

    def test_post_survives_audit_trail_failure(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')

        def _boom(*args, **kwargs):
            raise RuntimeError('audit boom')

        monkeypatch.setattr('routes.doctor.diagnosis.AuditTrail', _boom)
        resp = client.post(f'/doctor/diagnosis/{v.id}', data={'diagnosis': 'audit fails'})
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        db.session.expire_all()
        assert db.session.get(Visit, v.id).diagnosis == 'audit fails'

    def test_post_outer_exception_redirects_to_queue(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        _visit(db, p, doc, _department(db), status='IN_PROGRESS')

        class _BoomDb:
            class session:
                @staticmethod
                def execute(*args, **kwargs):
                    raise RuntimeError('db boom')

        monkeypatch.setattr('routes.doctor.diagnosis.db', _BoomDb())
        resp = client.get('/doctor/diagnosis/1')
        _assert_redirect_to(resp, '/doctor/patient-queue')

    def test_get_with_non_dict_json_vital_signs_renders(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        v.vital_signs = '[1, 2, 3]'
        db.session.commit()
        resp = client.get(f'/doctor/diagnosis/{v.id}')
        assert resp.status_code == 200

    def test_resave_updates_existing_follow_up_in_place(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        first_date = (date.today() + timedelta(days=10)).isoformat()
        second_date = (date.today() + timedelta(days=20)).isoformat()

        client.post(
            f'/doctor/diagnosis/{v.id}',
            data={
                'diagnosis': 'follow-up v1',
                'follow_up_required': 'on',
                'follow_up_date': first_date,
            },
        )
        rows = (
            db.session.execute(select(FollowUpRequest).filter_by(source_visit_id=v.id))
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].status == 'PENDING'
        first_id = rows[0].id
        assert rows[0].suggested_date.isoformat() == first_date

        client.post(
            f'/doctor/diagnosis/{v.id}',
            data={
                'diagnosis': 'follow-up v2',
                'follow_up_required': 'on',
                'follow_up_date': second_date,
            },
        )
        db.session.expire_all()
        rows = (
            db.session.execute(select(FollowUpRequest).filter_by(source_visit_id=v.id))
            .scalars()
            .all()
        )
        # re-save updates the existing request instead of adding a second one
        assert len(rows) == 1
        assert rows[0].id == first_id
        assert rows[0].suggested_date.isoformat() == second_date
        assert rows[0].status == 'PENDING'

    def test_resave_recreates_follow_up_after_previous_was_done(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        first_date = (date.today() + timedelta(days=10)).isoformat()
        second_date = (date.today() + timedelta(days=30)).isoformat()

        client.post(
            f'/doctor/diagnosis/{v.id}',
            data={
                'diagnosis': 'done-req',
                'follow_up_required': 'on',
                'follow_up_date': first_date,
            },
        )
        rows = (
            db.session.execute(select(FollowUpRequest).filter_by(source_visit_id=v.id))
            .scalars()
            .all()
        )
        assert len(rows) == 1
        rows[0].status = 'DONE'
        db.session.commit()

        client.post(
            f'/doctor/diagnosis/{v.id}',
            data={
                'diagnosis': 'done-req',
                'follow_up_required': 'on',
                'follow_up_date': second_date,
            },
        )
        db.session.expire_all()
        rows = (
            db.session.execute(select(FollowUpRequest).filter_by(source_visit_id=v.id))
            .scalars()
            .all()
        )
        assert len(rows) == 2
        statuses = sorted(r.status for r in rows)
        assert statuses == ['DONE', 'PENDING']


# ---------------------------------------------------------------------------
# Diagnosis: module-level "clinical AI" helpers
# ---------------------------------------------------------------------------


class TestClinicalAiHelpers:
    def test_analyze_returns_suggestions_when_history_exists(
        self, app, db, test_tenant, rollback_db
    ):
        doc = _make_doctor(db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        med = _medication(db, trade_name=f'AIDX-{_tag()}')
        rx = _prescription(db, p, doc, v)
        _rx_item(db, rx, med)
        db.session.add(
            MedicalRecord(
                patient_id=p.id,
                visit_id=v.id,
                title='تحليل',
                details='details',
                diagnosis=f'dx-{_tag()}',
                created_by=doc.id,
            )
        )
        db.session.commit()

        from routes.doctor import diagnosis as diagnosis_module

        with _bound_request(app, test_tenant, doc):
            out = diagnosis_module.get_ai_diagnostic_assistant()
        assert set(out) == {'common_diagnoses', 'common_medications', 'diagnostic_suggestions'}
        assert out['common_diagnoses'], 'expected at least one diagnosis row'
        assert out['common_medications'], 'expected at least one medication row'
        assert out['diagnostic_suggestions'], 'expected at least one suggestion'
        top = out['diagnostic_suggestions'][0]
        assert top['type'] == 'common_diagnosis'
        assert top['frequency'] >= 1

    def test_standardized_pathways_keyword_matching(self):
        from routes.doctor.diagnosis import get_standardized_pathways

        assert get_standardized_pathways('') == []
        assert get_standardized_pathways('   ') == []
        assert get_standardized_pathways('totally unrelated text') == []
        diabetes = get_standardized_pathways('patient with diabetes follow-up')
        assert any(path['id'] == 'diabetes_basic' for path in diabetes)
        assert get_standardized_pathways('السكري'), 'arabic keyword must match diabetes'

    def test_standardized_pathways_uti_and_asthma(self):
        from routes.doctor.diagnosis import get_standardized_pathways

        uti = get_standardized_pathways('uti symptoms')
        assert any(path['id'] == 'uti_basic' for path in uti)
        asthma = get_standardized_pathways('asthma attack')
        assert any(path['id'] == 'asthma_basic' for path in asthma)
        hype = get_standardized_pathways('hypertension')
        assert any(path['id'] == 'hypertension_basic' for path in hype)

    def test_data_based_recommendations_match_in_python(self, app, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        med = _medication(db, trade_name=f'REC-{_tag()}')
        for diag in (f'حالة-تجريبية-{_tag()}', None):
            rx = _prescription(db, p, doc, v, diagnosis=diag)
            _rx_item(db, rx, med)

        from routes.doctor import diagnosis as diagnosis_module

        with _bound_request(app, test_tenant, doc):
            recs = diagnosis_module.get_data_based_recommendations('حالة-تجريبية')
        assert recs, 'expected a matching recommendation'
        assert recs[0]['medication'] == med.trade_name
        assert recs[0]['count'] >= 1
        with _bound_request(app, test_tenant, doc):
            assert diagnosis_module.get_data_based_recommendations('لا-يوجد-شيء') == []
            assert diagnosis_module.get_data_based_recommendations('') == []

    def test_evaluate_clinical_rules_duplicate_medication(self, app, db, test_tenant, rollback_db):
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

    def test_evaluate_clinical_rules_allergy(self, app, db, test_tenant, rollback_db):
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

    def test_evaluate_clinical_rules_long_duration(self, app, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        med = _medication(db, trade_name=f'LONG-{_tag()}')
        rx = _prescription(db, p, doc, v)
        _rx_item(db, rx, med, duration_days=45)

        from routes.doctor.diagnosis import evaluate_clinical_rules

        warnings = evaluate_clinical_rules(v, [rx], {})
        assert any(w['type'] == 'long_duration' for w in warnings)

    def test_evaluate_clinical_rules_missing_vitals(self, app, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        p = _patient(db)
        for diag in ('hypertension follow-up', 'diabetes case'):
            v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
            v.diagnosis = diag
            db.session.commit()
            from routes.doctor.diagnosis import evaluate_clinical_rules

            warnings = evaluate_clinical_rules(v, [], {})
            assert any(w['type'] == 'missing_vitals' for w in warnings), diag
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        v.diagnosis = 'hypertension follow-up'
        db.session.commit()
        from routes.doctor.diagnosis import evaluate_clinical_rules

        assert evaluate_clinical_rules(v, [], {'blood_pressure': '135/85'}) == []

    def test_patient_medical_history_ai_aggregates(self, app, db, test_tenant, rollback_db):
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
        med = _medication(db, trade_name=f'LT-{_tag()}')
        for _ in range(4):
            rx = _prescription(db, p, doc, v0)
            _rx_item(db, rx, med)

        from routes.doctor import diagnosis as diagnosis_module

        with _bound_request(app, test_tenant, doc):
            out = diagnosis_module.get_patient_medical_history_ai()
        assert set(out) == {'frequent_patients', 'chronic_conditions', 'long_term_medications'}
        assert any(row['patient_id'] == p.id for row in out['frequent_patients'])
        assert any(row['condition'] == 'السكري' for row in out['chronic_conditions'])
        assert any(row['medication'] == med.trade_name for row in out['long_term_medications'])

    def test_treatment_recommendations_include_archived_success_and_interactions(
        self, app, db, test_tenant, rollback_db
    ):
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

        from routes.doctor.diagnosis import get_treatment_recommendations

        with _bound_request(app, test_tenant, doc):
            recs = get_treatment_recommendations()
        types = [r['type'] for r in recs]
        assert 'effective_treatment' in types
        assert 'drug_interaction' in types

    def test_drug_interaction_checker_flags_warfarin_aspirin(
        self, app, db, test_tenant, rollback_db
    ):
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
        assert out['total_prescriptions_checked'] >= 1
        names = {(i['medication1'], i['medication2']) for i in out['interactions_found']}
        assert ('وارفارين', 'أسبرين') in names
        assert out['interaction_rate'] > 0

    def test_clinical_decision_support_flags_low_success(self, app, db, test_tenant, rollback_db):
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

        from routes.doctor.diagnosis import get_clinical_decision_support

        with _bound_request(app, test_tenant, doc):
            recs = get_clinical_decision_support()
        types = [r['type'] for r in recs]
        assert 'diagnosis_improvement' in types
        assert 'medication_effectiveness' in types

    def test_medical_analytics_returns_metrics(self, app, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='COMPLETED', archive_status='ARCHIVED')
        _visit(db, p, doc, _department(db), status='OPEN')
        db.session.add(
            MedicalRecord(
                patient_id=p.id,
                visit_id=v.id,
                title='تحليل',
                details='d',
                diagnosis=f'حالة-إحصائية-{_tag()}',
                created_by=doc.id,
            )
        )
        med = _medication(db, trade_name=f'ANA-{_tag()}')
        rx = _prescription(db, p, doc, v)
        _rx_item(db, rx, med)

        from routes.doctor.diagnosis import get_medical_analytics

        with _bound_request(app, test_tenant, doc):
            out = get_medical_analytics()
        assert set(out) >= {
            'completion_rate',
            'avg_visit_duration',
            'diagnosis_distribution',
            'medication_distribution',
            'performance_score',
        }
        assert out['avg_visit_duration'] == 0
        assert out['completion_rate'] > 0
        assert any(row['medication'] == med.trade_name for row in out['medication_distribution'])

    def test_workflow_optimization_flags_peak_hours_and_heavy_day(
        self, app, db, test_tenant, rollback_db
    ):
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

    def test_smart_reminders_covers_all_three_channels(self, app, db, test_tenant, rollback_db):
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
        for _ in range(11):
            p_rx = _patient(db)
            v_rx = _visit(db, p_rx, doc, d, status='COMPLETED', archive_status='ARCHIVED')
            _prescription(db, p=p_rx, doc=doc, v=v_rx)
        db.session.commit()

        from routes.doctor.diagnosis import get_smart_reminders

        with _bound_request(app, test_tenant, doc):
            reminders = get_smart_reminders()
        types = [r['type'] for r in reminders]
        assert 'appointments' in types
        assert 'follow_up' in types
        assert 'medications' in types

    def test_check_drug_interactions_static_list(self):
        from routes.doctor.diagnosis import check_drug_interactions

        interactions = check_drug_interactions()
        assert len(interactions) == 3
        assert all(set(i) == {'drug1', 'drug2', 'severity'} for i in interactions)

    def test_calculate_medical_performance_score(self):
        from routes.doctor import calculate_medical_performance_score

        assert calculate_medical_performance_score(80, 120) == pytest.approx(70.0)
        assert calculate_medical_performance_score(80, 0) == pytest.approx(90.0)
        assert calculate_medical_performance_score(0, 10000) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Visits: route-level gap branches
# ---------------------------------------------------------------------------


class TestStartTreatmentGaps:
    def test_start_treatment_rejects_non_open_visit(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='COMPLETED')
        resp = client.post(f'/doctor/start-treatment/{v.id}')
        _assert_redirect_to(resp, '/doctor/patient-queue')
        db.session.expire_all()
        assert db.session.get(Visit, v.id).status == VisitState.COMPLETED.value

    def test_start_treatment_uses_users_department_fallback(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _make_doctor(db, test_tenant)
        dept = _department(db, name=f'FallbackDept-{_tag()}')
        doc.department_id = dept.id
        db.session.commit()
        _login_as(client, db, test_tenant, doc)
        p = _patient(db)
        v = _visit(db, p, doc, None, status='OPEN')
        ticket = _tick(db, v, dept, status='called')

        resp = client.post(f'/doctor/start-treatment/{v.id}')
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        db.session.expire_all()
        v2 = db.session.get(Visit, v.id)
        assert v2.department_id == dept.id
        assert v2.status == VisitState.IN_PROGRESS.value
        assert db.session.get(QueueManagement, ticket.id).status == 'in_progress'

    def test_start_treatment_uses_first_active_department_fallback(
        self, app, client, db, test_tenant, rollback_db
    ):
        from models.department import Department

        doc = _doctor_client(client, db, test_tenant)
        # doctor has no department_id; the route picks the first active dept
        first_active = (
            db.session.execute(
                select(Department).filter_by(is_active=True).order_by(Department.id.asc())
            )
            .scalars()
            .first()
        )
        if first_active is None:
            first_active = _department(db, name=f'FirstActive-{_tag()}')
        p = _patient(db)
        v = _visit(db, p, doc, None, status='OPEN')
        ticket = _tick(db, v, first_active, status='called')

        resp = client.post(f'/doctor/start-treatment/{v.id}')
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        db.session.expire_all()
        v2 = db.session.get(Visit, v.id)
        assert v2.department_id == first_active.id
        assert v2.status == VisitState.IN_PROGRESS.value
        assert db.session.get(QueueManagement, ticket.id).status == 'in_progress'

    def test_start_treatment_department_assignment_failure_flashes_error(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        _department(db, name=f'AssignFail-{_tag()}')
        v = _visit(db, p, doc, None, status='OPEN')

        def _boom(*args, **kwargs):
            raise RuntimeError('commit boom')

        monkeypatch.setattr('routes.doctor.visits.safe_commit', _boom)
        resp = client.post(f'/doctor/start-treatment/{v.id}')
        _assert_redirect_to(resp, '/doctor/patient-queue')

    def test_start_treatment_survives_audit_and_notification_failures(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='OPEN')
        _tick(db, v, d, status='called')

        def _boom(*args, **kwargs):
            raise RuntimeError('audit boom')

        monkeypatch.setattr('routes.doctor.visits.AuditTrail', _boom)
        monkeypatch.setattr(
            'services.notification_service.NotificationService.send_notification', _boom
        )
        resp = client.post(f'/doctor/start-treatment/{v.id}')
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        db.session.expire_all()
        assert db.session.get(Visit, v.id).status == VisitState.IN_PROGRESS.value

    def test_start_treatment_outer_exception_redirects_to_queue(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='OPEN')
        _tick(db, v, d, status='waiting')

        def _boom(*args, **kwargs):
            raise RuntimeError('queue service boom')

        monkeypatch.setattr(
            'services.queue_management_service.QueueManagementService.start_treatment', _boom
        )
        resp = client.post(f'/doctor/start-treatment/{v.id}')
        _assert_redirect_to(resp, '/doctor/patient-queue')
        db.session.expire_all()
        assert db.session.get(Visit, v.id).status == VisitState.OPEN.value


class TestEndTreatmentGaps:
    def test_end_treatment_visit_not_found_redirects(
        self, app, client, db, test_tenant, rollback_db
    ):
        _doctor_client(client, db, test_tenant)
        resp = client.post('/doctor/end-treatment/99999999')
        _assert_redirect_to(resp, '/doctor/patient-queue')

    def test_end_treatment_queue_completion_refusal_keeps_visit_open(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        _tick(db, v, d, status='in_progress')

        monkeypatch.setattr(
            'services.queue_management_service.QueueManagementService.complete_treatment',
            lambda *_args, **_kwargs: (False, 'blocked by gate'),
        )
        resp = client.post(f'/doctor/end-treatment/{v.id}')
        _assert_redirect_to(resp, '/doctor/patient-queue')
        db.session.expire_all()
        assert db.session.get(Visit, v.id).status == VisitState.IN_PROGRESS.value

    def test_end_treatment_survives_audit_and_notification_failures(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')

        def _boom(*args, **kwargs):
            raise RuntimeError('boom')

        monkeypatch.setattr('routes.doctor.visits.AuditTrail', _boom)
        monkeypatch.setattr(
            'services.notification_service.NotificationService.send_notification', _boom
        )
        resp = client.post(f'/doctor/end-treatment/{v.id}')
        _assert_redirect_to(resp, '/doctor/patient-queue')
        db.session.expire_all()
        assert db.session.get(Visit, v.id).status == VisitState.COMPLETED.value

    def test_end_treatment_outer_exception_redirects_to_queue(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')

        def _boom(visit, target, *, actor=None):
            raise RuntimeError('transition boom')

        monkeypatch.setattr(
            'services.visit_state_machine_service.VisitStateMachineService.transition', _boom
        )
        resp = client.post(f'/doctor/end-treatment/{v.id}')
        _assert_redirect_to(resp, '/doctor/patient-queue')


class TestSaveVisitSummaryGaps:
    def test_survives_follow_up_sync_failure(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')

        def _boom(visit, actor):
            raise RuntimeError('sync boom')

        monkeypatch.setattr('routes.doctor.visits._sync_follow_up_request_for_visit', _boom)
        resp = client.post(f'/doctor/save-visit-summary/{v.id}', json={'diagnosis': 'sync x'})
        assert resp.get_json()['success'] is True
        db.session.expire_all()
        assert db.session.get(Visit, v.id).diagnosis == 'sync x'

    def test_survives_audit_trail_failure(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')

        def _boom(*args, **kwargs):
            raise RuntimeError('audit boom')

        monkeypatch.setattr('routes.doctor.visits.AuditTrail', _boom)
        resp = client.post(f'/doctor/save-visit-summary/{v.id}', json={'diagnosis': 'audit x'})
        assert resp.get_json()['success'] is True

    def test_outer_exception_returns_500(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')

        def _boom(*args, **kwargs):
            raise RuntimeError('commit boom')

        monkeypatch.setattr('routes.doctor.visits.safe_commit', _boom)
        resp = client.post(f'/doctor/save-visit-summary/{v.id}', json={'diagnosis': 'boom'})
        assert resp.status_code == 500
        assert resp.get_json()['success'] is False


# ---------------------------------------------------------------------------
# Visits: patient-details critical counts and failure branches
# ---------------------------------------------------------------------------


class TestPatientDetailsGaps:
    def test_patient_details_counts_critical_lab_and_radiology(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(
            db,
            p,
            doc,
            d,
            status='IN_PROGRESS',
            notes='الزيارة قيد التنفيذ\n[مذكرة تحاليل] ملاحظة تحاليل\n[مذكرة تصوير] ملاحظة أشعة\n[ملاحظات طبية] ملاحظة عامة',
        )
        lr = LabRequest(
            visit_id=v.id,
            patient_id=p.id,
            requested_by=doc.id,
            status='REQUESTED',
            request_number=f'LR-{_tag()}',
        )
        db.session.add(lr)
        db.session.commit()
        db.session.add(
            LabResult(
                request_id=lr.id,
                patient_id=p.id,
                test_code='CBC',
                test_name='تحليل دم',
                value='3.0',
                status=LabResultStatus.VALIDATED.value,
                is_critical=True,
            )
        )
        rr = RadiologyRequest(
            visit_id=v.id,
            patient_id=p.id,
            requested_by=doc.id,
            modality='XR',
            body_part='chest',
            status='REQUESTED',
        )
        db.session.add(rr)
        db.session.commit()
        db.session.add(
            RadiologyResult(
                request_id=rr.id,
                patient_id=p.id,
                findings='shadow',
                impression='urgent',
                status=LabResultStatus.VALIDATED.value,
                is_critical=True,
            )
        )
        db.session.commit()

        resp = client.get(f'/doctor/patient-details/{v.id}')
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        # Critical counts are computed (lab + radiology each have 1 critical validated result).
        # The template renders alerts with "(1)" when the corresponding module is active.
        assert body.count('(1)') >= 1 or 'alert-danger' in body

    def test_patient_details_tolerates_broken_lab_models(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')

        monkeypatch.setitem(sys.modules, 'models.lab_request', None)
        resp = client.get(f'/doctor/patient-details/{v.id}')
        assert resp.status_code == 200

    def test_patient_details_outer_exception_redirects(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')

        def _boom(*args, **kwargs):
            raise RuntimeError('render boom')

        monkeypatch.setattr('routes.doctor.visits.render_template', _boom)
        resp = client.get(f'/doctor/patient-details/{v.id}')
        _assert_redirect_to(resp, '/doctor/patient-queue')


# ---------------------------------------------------------------------------
# Visits: module-level helper functions (direct unit tests)
# ---------------------------------------------------------------------------


class TestVisitsModuleHelpers:
    def test_parse_visit_vital_signs_variants(self):
        from ast import literal_eval

        from routes.doctor import visits as visits_module

        class _V:
            def __init__(self, raw):
                self.vital_signs = raw

        assert visits_module._parse_visit_vital_signs(_V(None)) == {}
        parsed = visits_module._parse_visit_vital_signs(
            _V(json.dumps({'blood_pressure': '120/80', 'heart_rate': 71}))
        )
        assert parsed['blood_pressure'] == '120/80'
        assert parsed['heart_rate'] == 71
        # literal_eval path: the vital signs column may hold a python dict repr
        py_dict = str({'blood_pressure': '118/76', 'heart_rate': 66, 'extra': 'ignored'})
        assert literal_eval(py_dict)
        parsed2 = visits_module._parse_visit_vital_signs(_V(py_dict))
        assert parsed2['blood_pressure'] == '118/76'
        assert 'extra' not in parsed2
        assert visits_module._parse_visit_vital_signs(_V('{{not-anything')) == {}

    def test_get_nurse_vital_signs_latest_and_missing(self, app, db, test_tenant, rollback_db):
        from routes.doctor import visits as visits_module

        p = _patient(db)
        assert visits_module._get_nurse_vital_signs(p.id) == (None, None)

        db.session.add(
            VitalSigns(
                patient_id=p.id,
                blood_pressure_systolic=130,
                blood_pressure_diastolic=85,
                heart_rate=72,
                temperature=36.6,
                respiratory_rate=14,
                oxygen_saturation=98,
                weight=70.5,
                height=175.0,
                notes='routine',
            )
        )
        db.session.commit()
        data, recorded_at = visits_module._get_nurse_vital_signs(p.id)
        assert recorded_at is not None
        assert data['blood_pressure'] == '130/85'
        assert data['heart_rate'] == 72
        assert data['oxygen_saturation'] == 98

    def test_get_visit_lab_data_counts_critical(self, app, db, test_tenant, rollback_db):
        from routes.doctor import visits as visits_module

        doc = _make_doctor(db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        reqs, critical = visits_module._get_visit_lab_data(v.id)
        assert reqs == []
        assert critical == 0

        lr = LabRequest(
            visit_id=v.id,
            patient_id=p.id,
            requested_by=doc.id,
            status='REQUESTED',
            request_number=f'LR-{_tag()}',
        )
        db.session.add(lr)
        db.session.commit()
        db.session.add(
            LabResult(
                request_id=lr.id,
                patient_id=p.id,
                test_code='K',
                test_name='K',
                value='6.9',
                status=LabResultStatus.VALIDATED.value,
                is_critical=True,
            )
        )
        db.session.commit()
        reqs, critical = visits_module._get_visit_lab_data(v.id)
        assert len(reqs) == 1
        assert critical == 1

    def test_get_visit_radiology_data_counts_critical(self, app, db, test_tenant, rollback_db):
        from routes.doctor import visits as visits_module

        doc = _make_doctor(db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        rr = RadiologyRequest(
            visit_id=v.id,
            patient_id=p.id,
            requested_by=doc.id,
            modality='CT',
            body_part='head',
            status='REQUESTED',
        )
        db.session.add(rr)
        db.session.commit()
        db.session.add(
            RadiologyResult(
                request_id=rr.id,
                patient_id=p.id,
                findings='acute',
                impression='critical',
                status=LabResultStatus.VALIDATED.value,
                is_critical=True,
            )
        )
        db.session.commit()
        reqs, critical = visits_module._get_visit_radiology_data(v.id)
        assert len(reqs) == 1
        assert critical == 1

    def test_count_visit_notes(self):
        from routes.doctor import visits as visits_module

        class _V:
            def __init__(self, notes):
                self.notes = notes

        assert visits_module._count_visit_notes(_V(None)) == (0, 0, 0, 0)
        note_count, lab, rad, general = visits_module._count_visit_notes(
            _V('السطر الأول\n[مذكرة تحاليل] سطر\n[مذكرة تصوير] سطر\n[ملاحظات طبية] سطر')
        )
        assert note_count == 4
        assert lab == 1
        assert rad == 1
        assert general == 1

    def test_get_current_prescriptions_limit_and_order(self, app, db, test_tenant, rollback_db):
        from routes.doctor import visits as visits_module

        doc = _make_doctor(db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        assert visits_module._get_current_prescriptions(v.id) == []
        for _ in range(3):
            _prescription(db, p, doc, v)
        assert len(visits_module._get_current_prescriptions(v.id)) == 3

    def test_recent_other_visits_and_medical_records_and_allergies(
        self, app, db, test_tenant, rollback_db
    ):
        from routes.doctor import visits as visits_module

        doc = _make_doctor(db, test_tenant)
        p = _patient(db)
        d = _department(db)
        current = _visit(db, p, doc, d, status='IN_PROGRESS')
        other = _visit(db, p, doc, d, status='COMPLETED')
        db.session.add(PatientAllergy(patient_id=p.id, allergen='histamine-x'))
        db.session.add(
            MedicalRecord(
                patient_id=p.id, visit_id=other.id, title='سجل', details='d', created_by=doc.id
            )
        )
        db.session.commit()

        with _bound_request(app, test_tenant, doc):
            others = visits_module._get_recent_other_visits(p.id, current.id)
        assert [x.id for x in others] == [other.id]

        allergies = visits_module._get_patient_allergies(p.id)
        assert any(a.allergen == 'histamine-x' for a in allergies)

        records = visits_module._get_patient_medical_records(p.id)
        assert any(r.title == 'سجل' for r in records)

        meds = visits_module._get_patient_prescriptions(p.id)
        assert meds == []

    def test_visit_summary_page_renders_for_completed_visit(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='COMPLETED')
        resp = client.get(f'/doctor/visit-summary/{v.id}')
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Patient queue / appointments / dashboard gaps
# ---------------------------------------------------------------------------


class TestPatientQueueGaps:
    def test_queue_renders_when_queue_model_broken(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        _visit(db, p, doc, _department(db), status='OPEN')

        monkeypatch.setitem(sys.modules, 'models.queue_management', None)
        resp = client.get('/doctor/patient-queue')
        assert resp.status_code == 200

    def test_queue_outer_exception_redirects_to_dashboard(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        _doctor_client(client, db, test_tenant)

        def _boom(*args, **kwargs):
            raise RuntimeError('render boom')

        monkeypatch.setattr('routes.doctor.queue.render_template', _boom)
        resp = client.get('/doctor/patient-queue')
        _assert_redirect_to(resp, '/doctor/dashboard')

    def test_call_patient_outer_exception_redirects(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='OPEN')
        _tick(db, v, d, status='waiting')

        def _boom(*args, **kwargs):
            raise RuntimeError('commit boom')

        monkeypatch.setattr(db.session, 'commit', _boom)
        resp = client.post(f'/doctor/call-patient/{v.id}')
        _assert_redirect_to(resp, '/doctor/patient-queue')
        db.session.expire_all()
        t = db.session.execute(select(QueueManagement).filter_by(visit_id=v.id)).scalars().first()
        assert t.status == 'waiting'


class TestAppointmentsGaps:
    def test_appointments_outer_exception_redirects_to_dashboard(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        _doctor_client(client, db, test_tenant)

        def _boom(*args, **kwargs):
            raise RuntimeError('render boom')

        monkeypatch.setattr('routes.doctor.appointments.render_template', _boom)
        resp = client.get('/doctor/appointments')
        _assert_redirect_to(resp, '/doctor/dashboard')


class TestDashboardGaps:
    def test_dashboard_new_outer_exception_redirects(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        _doctor_client(client, db, test_tenant)

        def _boom(*args, **kwargs):
            raise RuntimeError('render boom')

        monkeypatch.setattr('routes.doctor.dashboard.render_template', _boom)
        resp = client.get('/doctor/dashboard-new')
        _assert_redirect_to(resp, '/doctor/patient-queue')

    def test_dashboard_command_center_failure_redirects(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        _doctor_client(client, db, test_tenant)

        def _boom(user):
            raise RuntimeError('command center boom')

        monkeypatch.setattr('app.shared.dashboard_service.render_command_center', _boom)
        resp = client.get('/doctor/dashboard')
        _assert_redirect_to(resp, '/doctor/patient-queue')

    def test_dashboard_for_doctor_earnings_from_pricing(
        self, app, client, db, test_tenant, rollback_db
    ):
        from models.pricing import DoctorPricing

        target = _make_doctor(db, test_tenant, username=f'wv2_earn_{_tag()}')
        p = _patient(db)
        d = _department(db)
        db.session.add(
            DoctorPricing(
                doctor_id=target.id,
                department_id=d.id,
                consultation_price=60,
                follow_up_price=40,
                emergency_price=50,
                is_active=True,
                effective_from=datetime.now(UTC) - timedelta(days=30),
            )
        )
        db.session.commit()
        _visit(db, p, target, d, status='COMPLETED', visit_type='CONSULTATION', total_amount=100)
        _visit(db, p, target, d, status='COMPLETED', visit_type='FOLLOW_UP', total_amount=100)
        _visit(
            db,
            p,
            target,
            d,
            status='COMPLETED',
            visit_type='REGULAR',
            total_amount=100,
            is_emergency=True,
        )
        manager = ensure_test_user(
            db, test_tenant, username=f'{_MANAGER_USER}_{_tag()}', role='manager'
        )
        _login_as(client, db, test_tenant, manager)
        resp = client.get(f'/doctor/dashboard/{target.id}')
        assert resp.status_code == 200

    def test_dashboard_for_doctor_earnings_failure_zeros(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        target = _make_doctor(db, test_tenant, username=f'wv2_earn0_{_tag()}')
        manager = ensure_test_user(
            db, test_tenant, username=f'{_MANAGER_USER}_{_tag()}', role='manager'
        )
        _login_as(client, db, test_tenant, manager)

        monkeypatch.setitem(sys.modules, 'models.pricing', None)
        resp = client.get(f'/doctor/dashboard/{target.id}')
        assert resp.status_code == 200

    def test_dashboard_for_doctor_outer_exception_redirects(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        target = _make_doctor(db, test_tenant, username=f'wv2_dbx_{_tag()}')
        manager = ensure_test_user(
            db, test_tenant, username=f'{_MANAGER_USER}_{_tag()}', role='manager'
        )
        _login_as(client, db, test_tenant, manager)

        def _boom(*args, **kwargs):
            raise RuntimeError('render boom')

        monkeypatch.setattr('routes.doctor.dashboard.render_template', _boom)
        resp = client.get(f'/doctor/dashboard/{target.id}')
        _assert_redirect_to(resp, '/dashboard')

    def test_api_dashboard_stats_outer_exception_returns_500(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        _doctor_client(client, db, test_tenant)

        class _BoomSession:
            @staticmethod
            def execute(*args, **kwargs):
                raise RuntimeError('db boom')

        class _BoomDb:
            session = _BoomSession()

        monkeypatch.setattr('routes.doctor.dashboard.db', _BoomDb())
        resp = client.get('/doctor/api/dashboard-stats')
        assert resp.status_code == 500
        assert resp.get_json()['success'] is False

    def test_api_today_visits_outer_exception_returns_500(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        _doctor_client(client, db, test_tenant)

        class _BoomSession:
            @staticmethod
            def execute(*args, **kwargs):
                raise RuntimeError('db boom')

        class _BoomDb:
            session = _BoomSession()

        monkeypatch.setattr('routes.doctor.dashboard.db', _BoomDb())
        resp = client.get('/doctor/api/today-visits')
        assert resp.status_code == 500
        assert resp.get_json()['success'] is False


# ---------------------------------------------------------------------------
# Disabled-module redirects (lab / radiology / billing), isolated tenants
# ---------------------------------------------------------------------------


class TestModuleDisabledRedirects:
    def test_lab_request_module_disabled_redirects(self, app, client, db, isolated_tenant):
        _disable_module(app, isolated_tenant, 'lab')
        doc = ensure_test_user(db, isolated_tenant, username=f'wv2_laboff_{_tag()}', role='doctor')
        login_test_client(client, doc, isolated_tenant, 'ValidPass123!')
        resp = client.get('/doctor/lab-request/1')
        _assert_redirect_to(resp, '/doctor/patient-queue')

    def test_radiology_request_module_disabled_redirects(self, app, client, db, isolated_tenant):
        _disable_module(app, isolated_tenant, 'radiology')
        doc = ensure_test_user(db, isolated_tenant, username=f'wv2_radoff_{_tag()}', role='doctor')
        login_test_client(client, doc, isolated_tenant, 'ValidPass123!')
        resp = client.get('/doctor/radiology-request/1')
        _assert_redirect_to(resp, '/doctor/patient-queue')

    def test_print_invoice_billing_disabled_redirects(self, app, client, db, isolated_tenant):
        _disable_module(app, isolated_tenant, 'billing')
        doc = ensure_test_user(db, isolated_tenant, username=f'wv2_billoff_{_tag()}', role='doctor')
        login_test_client(client, doc, isolated_tenant, 'ValidPass123!')
        resp = client.get('/doctor/print-invoice/1')
        _assert_redirect_to(resp, '/dashboard')

    def test_print_receipt_billing_disabled_redirects(self, app, client, db, isolated_tenant):
        _disable_module(app, isolated_tenant, 'billing')
        doc = ensure_test_user(
            db, isolated_tenant, username=f'wv2_billoff2_{_tag()}', role='doctor'
        )
        login_test_client(client, doc, isolated_tenant, 'ValidPass123!')
        resp = client.get('/doctor/print-receipt/1')
        _assert_redirect_to(resp, '/dashboard')


# ---------------------------------------------------------------------------
# Lab surface gaps
# ---------------------------------------------------------------------------


class TestLabRequestGaps:
    def test_lab_request_missing_visit_redirects(self, app, client, db, test_tenant, rollback_db):
        _doctor_client(client, db, test_tenant)
        resp = client.get('/doctor/lab-request/99999999')
        _assert_redirect_to(resp, '/doctor/patient-queue')

    def test_lab_request_oversized_notes_redirects(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        resp = client.post(
            f'/doctor/lab-request/{v.id}',
            data={'test_name': 'CBC', 'notes': 'x' * 2001},
        )
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        db.session.expire_all()
        assert not db.session.get(Visit, v.id).lab_tests_ordered

    def test_lab_request_oversized_urgency_redirects(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        resp = client.post(
            f'/doctor/lab-request/{v.id}',
            data={'test_name': 'CBC', 'urgency': 'x' * 51},
        )
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        db.session.expire_all()
        assert not db.session.get(Visit, v.id).lab_tests_ordered

    def test_lab_request_structured_failure_flashes_warning(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')

        from services.lab_service import lab_service as _lab_svc

        monkeypatch.setattr(
            _lab_svc,
            'create_request',
            lambda **_kwargs: (False, {'error': 'catalog unavailable'}),
        )
        resp = client.post(
            f'/doctor/lab-request/{v.id}',
            data={'test_ids': '12345'},
            follow_redirects=False,
        )
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        db.session.expire_all()
        assert db.session.get(Visit, v.id).lab_tests_ordered

    def test_lab_request_survives_handoff_failure(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')

        monkeypatch.setitem(sys.modules, 'models.department', None)
        resp = client.post(f'/doctor/lab-request/{v.id}', data={'test_name': 'CBC'})
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        db.session.expire_all()
        v2 = db.session.get(Visit, v.id)
        assert v2.lab_tests_ordered
        assert not v2.pending_financial_settlement

    def test_lab_request_survives_audit_failure(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')

        def _boom(*args, **kwargs):
            raise RuntimeError('audit boom')

        monkeypatch.setattr('routes.doctor.lab.AuditTrail', _boom)
        resp = client.post(f'/doctor/lab-request/{v.id}', data={'test_name': 'CBC'})
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')

    def test_lab_request_outer_exception_redirects(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')

        def _boom(*args, **kwargs):
            raise RuntimeError('commit boom')

        monkeypatch.setattr('routes.doctor.lab.safe_commit', _boom)
        resp = client.post(f'/doctor/lab-request/{v.id}', data={'test_name': 'CBC'})
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')

    def test_lab_results_tolerates_broken_results_model(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db, first_name='LabBroken')
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        lr = LabRequest(
            visit_id=v.id,
            patient_id=p.id,
            requested_by=doc.id,
            status='REQUESTED',
            request_number=f'LR-{_tag()}',
        )
        db.session.add(lr)
        db.session.commit()

        monkeypatch.setitem(sys.modules, 'models.lab_request', None)
        resp = client.get(f'/doctor/lab-results/{p.id}')
        assert resp.status_code == 200
        assert 'LabBroken' in resp.get_data(as_text=True)

    def test_lab_results_outer_exception_redirects(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        _visit(db, p, doc, _department(db), status='IN_PROGRESS')

        def _boom(*args, **kwargs):
            raise RuntimeError('render boom')

        monkeypatch.setattr('routes.doctor.lab.render_template', _boom)
        resp = client.get(f'/doctor/lab-results/{p.id}')
        _assert_redirect_to(resp, '/doctor/patient-queue')


# ---------------------------------------------------------------------------
# Radiology surface gaps
# ---------------------------------------------------------------------------


class TestRadiologyRequestGaps:
    def test_radiology_missing_visit_redirects(self, app, client, db, test_tenant, rollback_db):
        _doctor_client(client, db, test_tenant)
        resp = client.get('/doctor/radiology-request/99999999')
        _assert_redirect_to(resp, '/doctor/patient-queue')

    def test_radiology_oversized_test_name_redirects(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        resp = client.post(f'/doctor/radiology-request/{v.id}', data={'test_name': 'x' * 201})
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        db.session.expire_all()
        assert not db.session.get(Visit, v.id).radiology_ordered

    def test_radiology_oversized_notes_redirects(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        resp = client.post(
            f'/doctor/radiology-request/{v.id}',
            data={'test_name': 'XR', 'notes': 'x' * 2001},
        )
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')

    def test_radiology_oversized_body_part_redirects(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        resp = client.post(
            f'/doctor/radiology-request/{v.id}',
            data={'body_part': 'x' * 201},
        )
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')

    def test_radiology_structured_failure_flashes_warning(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')

        from services.radiology_service import radiology_service as _rad_svc

        monkeypatch.setattr(
            _rad_svc,
            'create_request',
            lambda **_kwargs: (False, {'error': 'catalog unavailable'}),
        )
        resp = client.post(
            f'/doctor/radiology-request/{v.id}',
            data={'modality': 'XR', 'body_part': 'chest'},
        )
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        db.session.expire_all()
        v2 = db.session.get(Visit, v.id)
        assert v2.radiology_ordered

    def test_radiology_missing_reception_department_skips_handoff(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        from models.department import Department

        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')

        monkeypatch.setattr(Department, 'get_type', lambda _self: 'clinic')
        resp = client.post(f'/doctor/radiology-request/{v.id}', data={'test_name': 'XR'})
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        db.session.expire_all()
        v2 = db.session.get(Visit, v.id)
        assert v2.radiology_ordered
        assert not v2.pending_financial_settlement

    def test_radiology_survives_handoff_failure(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')

        monkeypatch.setitem(sys.modules, 'models.department', None)
        resp = client.post(f'/doctor/radiology-request/{v.id}', data={'test_name': 'XR'})
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        db.session.expire_all()
        assert db.session.get(Visit, v.id).radiology_ordered

    def test_radiology_survives_audit_failure(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')

        def _boom(*args, **kwargs):
            raise RuntimeError('audit boom')

        monkeypatch.setattr('routes.doctor.radiology.AuditTrail', _boom)
        resp = client.post(f'/doctor/radiology-request/{v.id}', data={'test_name': 'XR'})
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')

    def test_radiology_outer_exception_redirects(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')

        def _boom(*args, **kwargs):
            raise RuntimeError('commit boom')

        monkeypatch.setattr('routes.doctor.radiology.safe_commit', _boom)
        resp = client.post(f'/doctor/radiology-request/{v.id}', data={'test_name': 'XR'})
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')

    def test_radiology_results_renders_with_critical_result(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db, first_name='RadCritical')
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        rr = RadiologyRequest(
            visit_id=v.id,
            patient_id=p.id,
            requested_by=doc.id,
            modality='MRI',
            body_part='brain',
            status='REQUESTED',
        )
        db.session.add(rr)
        db.session.commit()
        db.session.add(
            RadiologyResult(
                request_id=rr.id,
                patient_id=p.id,
                findings='large hemorrhage',
                impression='critical',
                status=LabResultStatus.VALIDATED.value,
                is_critical=True,
            )
        )
        db.session.commit()
        resp = client.get(f'/doctor/radiology-results/{p.id}')
        assert resp.status_code == 200

    def test_radiology_results_tolerates_broken_results_model(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db, first_name='RadBroken')
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        db.session.add(
            RadiologyRequest(
                visit_id=v.id,
                patient_id=p.id,
                requested_by=doc.id,
                modality='XR',
                body_part='chest',
                status='REQUESTED',
            )
        )
        db.session.commit()

        monkeypatch.setitem(sys.modules, 'models.radiology_result', None)
        resp = client.get(f'/doctor/radiology-results/{p.id}')
        assert resp.status_code == 200

    def test_radiology_results_outer_exception_redirects(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        _visit(db, p, doc, _department(db), status='IN_PROGRESS')

        def _boom(*args, **kwargs):
            raise RuntimeError('render boom')

        monkeypatch.setattr('routes.doctor.radiology.render_template', _boom)
        resp = client.get(f'/doctor/radiology-results/{p.id}')
        _assert_redirect_to(resp, '/doctor/patient-queue')


# ---------------------------------------------------------------------------
# Prescriptions surface gaps
# ---------------------------------------------------------------------------


class TestPrescriptionItemParsing:
    def test_item_medication_refs_with_pipe_and_garbage(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        med = _medication(db)
        resp = client.post(
            f'/doctor/prescription/{v.id}',
            data={
                'item_medication_ref[]': [f'{med.id}|label', 'no-pipe-here', ''],
                'item_dosage[]': ['5mg', '1mg', '2mg'],
                'item_frequency[]': ['daily', 'daily', 'daily'],
                'item_duration_days[]': ['7', '7', '7'],
                'item_quantity[]': ['1', '1', '1'],
                'item_instructions[]': ['', '', ''],
            },
        )
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        rx = db.session.execute(select(Prescription).filter_by(visit_id=v.id)).scalars().first()
        assert rx is not None
        items = rx.items.all()
        # 'no-pipe-here' parses to an empty id (skipped); the blank ref is skipped
        assert len(items) == 1
        assert items[0].medication_id == med.id

    def test_legacy_unknown_medication_all_fields_goes_non_catalog(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        resp = client.post(
            f'/doctor/prescription/{v.id}',
            data={
                'medication_name': f'LegacyUnknownDrug-{_tag()}',
                'dosage': '5mg',
                'frequency': 'twice daily',
                'duration': '10 days',
                'instructions': 'after meals',
            },
        )
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        rx = db.session.execute(select(Prescription).filter_by(visit_id=v.id)).scalars().first()
        assert rx is not None
        assert rx.items.count() == 0
        notes = rx.notes or ''
        assert 'twice daily' in notes
        assert '10 days' in notes
        assert 'after meals' in notes

    def test_legacy_lookup_error_goes_non_catalog(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')

        import models.medication as medication_module

        orig_trade_name = medication_module.Medication.trade_name

        class _BoomIlike:
            def ilike(self, _value):
                raise AttributeError('forced lookup failure')

            def __getattr__(self, name):
                return getattr(orig_trade_name, name)

        # Break the legacy name lookup query without poisoning unrelated column operations.
        monkeypatch.setattr(medication_module.Medication, 'trade_name', _BoomIlike(), raising=False)
        resp = client.post(
            f'/doctor/prescription/{v.id}',
            data={
                'medication_name': f'LegacyBoomDrug-{_tag()}',
                'dosage': '5mg',
                'frequency': 'daily',
                'duration': '7 days',
            },
        )
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')

    def test_additional_notes_recorded_on_prescription(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        med = _medication(db)
        data = _rx_form([med.id])
        data['additional_notes'] = 'coverage-note-unique-zzz'
        resp = client.post(f'/doctor/prescription/{v.id}', data=data)
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        rx = db.session.execute(select(Prescription).filter_by(visit_id=v.id)).scalars().first()
        assert 'coverage-note-unique-zzz' in (rx.notes or '')

    def test_blank_invalid_and_unknown_med_ids_are_skipped(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        med = _medication(db)
        data = {
            'item_medication_id[]': ['', 'not-a-number', '999999999', str(med.id)],
            'item_dosage[]': ['5mg', '5mg', '5mg', '5mg'],
            'item_frequency[]': ['daily', 'daily', 'daily', 'daily'],
            'item_duration_days[]': ['7', '7', '7', '7'],
            'item_quantity[]': ['1', '1', '1', '1'],
            'item_instructions[]': ['', '', '', ''],
        }
        resp = client.post(f'/doctor/prescription/{v.id}', data=data)
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        rx = db.session.execute(select(Prescription).filter_by(visit_id=v.id)).scalars().first()
        assert rx is not None
        items = rx.items.all()
        assert len(items) == 1
        assert items[0].medication_id == med.id

    def test_standard_instructions_fallback_when_item_blank(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        med = _medication(db, standard_instructions='Take with water-zzz')
        data = _rx_form([med.id])
        resp = client.post(f'/doctor/prescription/{v.id}', data=data)
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        rx = db.session.execute(select(Prescription).filter_by(visit_id=v.id)).scalars().first()
        assert rx.items.all()[0].instructions == 'Take with water-zzz'

    def test_rows_with_missing_dosage_or_bad_duration_are_skipped(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        med_ok = _medication(db, trade_name=f'OkMed-{_tag()}')
        med_nodose = _medication(db, trade_name=f'NoDose-{_tag()}')
        med_baddur = _medication(db, trade_name=f'BadDur-{_tag()}')
        data = {
            'item_medication_id[]': [str(med_ok.id), str(med_nodose.id), str(med_baddur.id)],
            'item_dosage[]': ['5mg', '', '5mg'],
            'item_frequency[]': ['daily', 'daily', 'daily'],
            'item_duration_days[]': ['7', '7', 'not-a-number'],
            'item_quantity[]': ['2', '2', '2'],
            'item_instructions[]': ['', '', ''],
        }
        resp = client.post(f'/doctor/prescription/{v.id}', data=data)
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        rx = db.session.execute(select(Prescription).filter_by(visit_id=v.id)).scalars().first()
        kept = {item.medication_id for item in rx.items.all()}
        assert kept == {med_ok.id}

    def test_non_numeric_and_negative_quantity_coerced_to_one(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        med = _medication(db)
        med2 = _medication(db, trade_name=f'Qty2-{_tag()}')
        data = {
            'item_medication_id[]': [str(med.id), str(med2.id)],
            'item_dosage[]': ['5mg', '5mg'],
            'item_frequency[]': ['daily', 'daily'],
            'item_duration_days[]': ['7', '7'],
            'item_quantity[]': ['not-a-number', '-4'],
            'item_instructions[]': ['', ''],
        }
        resp = client.post(f'/doctor/prescription/{v.id}', data=data)
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        rx = db.session.execute(select(Prescription).filter_by(visit_id=v.id)).scalars().first()
        quantities = sorted(item.quantity for item in rx.items.all())
        assert quantities == [1, 1]

    def test_empty_allergen_row_does_not_trip_warning(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        db.session.add(PatientAllergy(patient_id=p.id, allergen=''))
        db.session.commit()
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        med = _medication(db)
        resp = client.post(f'/doctor/prescription/{v.id}', data=_rx_form([med.id]))
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')

    def test_allergy_query_failure_still_writes_prescription(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        import sqlalchemy

        real_select = sqlalchemy.select

        def _fake_select(*args, **kwargs):
            if len(args) == 1 and getattr(args[0], '__tablename__', '') == 'patient_allergies':
                raise RuntimeError('allergy lookup boom')
            return real_select(*args, **kwargs)

        monkeypatch.setattr('routes.doctor.prescriptions.select', _fake_select)
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        med = _medication(db)
        resp = client.post(f'/doctor/prescription/{v.id}', data=_rx_form([med.id]))
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        rx = db.session.execute(select(Prescription).filter_by(visit_id=v.id)).scalars().first()
        assert rx is not None
        assert rx.items.count() == 1

    def test_missing_reception_department_leaves_visit_in_place(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        monkeypatch.setitem(sys.modules, 'models.department', None)
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        med = _medication(db)
        resp = client.post(f'/doctor/prescription/{v.id}', data=_rx_form([med.id]))
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        db.session.expire_all()
        assert db.session.get(Visit, v.id).pending_financial_settlement is not True


class TestPrescriptionNonCatalogAndTemplates:
    def test_notify_pharmacy_swallows_notification_errors(
        self, app, db, test_tenant, rollback_db, monkeypatch
    ):
        from routes.doctor.prescriptions import _notify_pharmacy_non_catalog

        doc = _make_doctor(db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')

        monkeypatch.setitem(sys.modules, 'models.notification', None)
        # must not raise even when the notification model is unavailable
        _notify_pharmacy_non_catalog('SomeNewDrug', v, doc)

    def test_drug_interaction_warnings_swallow_errors(self, monkeypatch):
        from routes.doctor.prescriptions import _check_drug_interaction_warnings

        assert _check_drug_interaction_warnings({'not-an-int'}) == []

    def test_prescription_page_survives_broken_templates_config(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        from models.system_config import SystemConfig

        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')

        def _boom(self):
            raise RuntimeError('config boom')

        monkeypatch.setattr(SystemConfig, 'get_value', _boom)
        resp = client.get(f'/doctor/prescription/{v.id}')
        assert resp.status_code == 200

    def test_save_as_template_with_medication_lookup_failure_still_saves(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        from models.system_config import SystemConfig

        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        med = _medication(db)
        data = _rx_form([med.id])
        data['save_as_template'] = 'on'
        data['template_name'] = f'tpl-{_tag()}'

        monkeypatch.setattr(
            'models.medication.PrescriptionItem.medication',
            property(fget=lambda _self: (_ for _ in ()).throw(RuntimeError('medication boom'))),
        )
        resp = client.post(f'/doctor/prescription/{v.id}', data=data)
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')

        rx = db.session.execute(select(Prescription).filter_by(visit_id=v.id)).scalars().first()
        assert rx is not None
        cfg = (
            db.session.execute(
                select(SystemConfig).filter_by(config_key=f'doctor_rx_templates_{doc.id}')
            )
            .scalars()
            .first()
        )
        assert cfg is not None
        templates = cfg.get_value()
        assert templates and templates[0]['items'][0]['medication_label'] == ''

    def test_save_as_template_with_non_list_config_resets(
        self, app, client, db, test_tenant, rollback_db
    ):
        from models.system_config import SystemConfig

        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        med = _medication(db)
        db.session.add(
            SystemConfig(
                config_key=f'doctor_rx_templates_{doc.id}',
                tenant_id=test_tenant.id,
                config_type='json',
                config_value='{"not": "a list"}',
                category='general',
                description='test cfg',
                is_system=False,
                is_encrypted=False,
            )
        )
        db.session.commit()
        data = _rx_form([med.id])
        data['save_as_template'] = 'on'
        data['template_name'] = f'tpl-{_tag()}'
        resp = client.post(f'/doctor/prescription/{v.id}', data=data)
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')

        cfg = (
            db.session.execute(
                select(SystemConfig).filter_by(config_key=f'doctor_rx_templates_{doc.id}')
            )
            .scalars()
            .first()
        )
        templates = cfg.get_value()
        assert isinstance(templates, list)
        assert any(t.get('name', '').startswith('tpl-') for t in templates)

    def test_save_as_template_set_value_failure_still_writes_prescription(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        from models.system_config import SystemConfig

        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        med = _medication(db)

        def _boom(self, value):
            raise RuntimeError('set_value boom')

        monkeypatch.setattr(SystemConfig, 'set_value', _boom)
        data = _rx_form([med.id])
        data['save_as_template'] = 'on'
        data['template_name'] = f'tpl-{_tag()}'
        resp = client.post(f'/doctor/prescription/{v.id}', data=data)
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        rx = db.session.execute(select(Prescription).filter_by(visit_id=v.id)).scalars().first()
        assert rx is not None

    def test_audit_commit_failure_still_writes_prescription(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        from utils import db_safety

        real_safe_commit = db_safety.safe_commit
        state = {'n': 0}

        def _flaky(session, **kwargs):
            state['n'] += 1
            if state['n'] == 2:
                raise RuntimeError('audit commit boom')
            return real_safe_commit(session, **kwargs)

        monkeypatch.setattr('routes.doctor.prescriptions.safe_commit', _flaky)
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        med = _medication(db)
        resp = client.post(f'/doctor/prescription/{v.id}', data=_rx_form([med.id]))
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        rx = db.session.execute(select(Prescription).filter_by(visit_id=v.id)).scalars().first()
        assert rx is not None
        assert rx.items.count() == 1


class TestPrescriptionPrintGaps:
    def _rx_for(self, db, p, doc, v):
        return _prescription(db, p, doc, v, status='active')

    def test_print_prescription_qr_failure_redirects(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        def _boom(payload):
            raise RuntimeError('qr boom')

        monkeypatch.setattr('routes.doctor.prescriptions.generate_qr_data_uri', _boom)
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')
        rx = self._rx_for(db, p, doc, v)
        resp = client.get(f'/doctor/print-prescription/{rx.id}')
        _assert_redirect_to(resp, '/doctor/patient-queue')

    def test_prescriptions_list_outer_exception_redirects_to_dashboard(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        _doctor_client(client, db, test_tenant)

        def _boom(*args, **kwargs):
            raise RuntimeError('render boom')

        monkeypatch.setattr('routes.doctor.prescriptions.render_template', _boom)
        resp = client.get('/doctor/prescriptions')
        _assert_redirect_to(resp, '/doctor/dashboard')

    def test_print_invoice_visit_lookup_failure_redirects(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        from utils import tenant_query

        real_get = tenant_query.get_tenant_record
        calls = {'n': 0}

        def _flaky(model, record_id):
            calls['n'] += 1
            if calls['n'] == 1:
                return real_get(model, record_id)
            raise tenant_query.TenantContextError('forced tenant context loss')

        monkeypatch.setattr('utils.tenant_query.get_tenant_record', _flaky)
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='COMPLETED', total_amount=120)
        inv = Invoice(visit_id=v.id, total_amount=120, paid_amount=0, status='ISSUED')
        db.session.add(inv)
        db.session.commit()
        resp = client.get(f'/doctor/print-invoice/{inv.id}')
        _assert_redirect_to(resp, '/doctor/patient-queue')

    def test_print_invoice_qr_failure_redirects(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        def _boom(payload):
            raise RuntimeError('qr boom')

        monkeypatch.setattr('routes.doctor.prescriptions.generate_qr_data_uri', _boom)
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='COMPLETED', total_amount=120)
        inv = Invoice(visit_id=v.id, total_amount=120, paid_amount=0, status='ISSUED')
        db.session.add(inv)
        db.session.commit()
        resp = client.get(f'/doctor/print-invoice/{inv.id}')
        _assert_redirect_to(resp, '/doctor/patient-queue')

    def test_print_receipt_visit_lookup_failure_redirects(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        from utils import tenant_query

        def _boom(model, record_id):
            raise tenant_query.TenantContextError('forced tenant context loss')

        monkeypatch.setattr('utils.tenant_query.get_tenant_record', _boom)
        _doctor_client(client, db, test_tenant)
        resp = client.get('/doctor/print-receipt/1')
        _assert_redirect_to(resp, '/doctor/patient-queue')

    def test_print_receipt_missing_visit_redirects(self, app, client, db, test_tenant, rollback_db):
        _doctor_client(client, db, test_tenant)
        resp = client.get('/doctor/print-receipt/99999999')
        _assert_redirect_to(resp, '/doctor/patient-queue')

    def test_print_receipt_qr_failure_redirects(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        def _boom(payload):
            raise RuntimeError('qr boom')

        monkeypatch.setattr('routes.doctor.prescriptions.generate_qr_data_uri', _boom)
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='COMPLETED', total_amount=75)
        resp = client.get(f'/doctor/print-receipt/{v.id}')
        _assert_redirect_to(resp, '/doctor/patient-queue')


# ---------------------------------------------------------------------------
# Dental chart / patients / notes / templates gaps
# ---------------------------------------------------------------------------


class TestDentalChartGaps:
    def test_dental_chart_page_renders_saved_teeth(self, app, client, db, test_tenant, rollback_db):
        _doctor_client(client, db, test_tenant)
        p = _patient(db)
        client.post(
            '/doctor/dental-chart/save',
            json={
                'patient_id': p.id,
                'visit_id': None,
                'teeth': {
                    '11': {'state': 'caries', 'surfaces': {'occlusal': 'caries'}, 'notes': 'ملاحظة'}
                },
                'notes': 'chart-note',
            },
        )
        resp = client.get(f'/doctor/dental-chart/{p.id}')
        assert resp.status_code == 200

    def test_dental_chart_save_outer_exception_returns_500(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        _doctor_client(client, db, test_tenant)
        p = _patient(db)

        def _boom(*args, **kwargs):
            raise RuntimeError('commit boom')

        monkeypatch.setattr('routes.doctor.patients.safe_commit', _boom)
        resp = client.post(
            '/doctor/dental-chart/save',
            json={'patient_id': p.id, 'teeth': {'11': {'state': 'caries'}}},
        )
        assert resp.status_code == 500
        assert resp.get_json()['success'] is False


class TestPatientsSurfaceGaps:
    def test_medical_history_outer_exception_redirects(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        _doctor_client(client, db, test_tenant)
        p = _patient(db)

        def _boom(*args, **kwargs):
            raise RuntimeError('render boom')

        monkeypatch.setattr('routes.doctor.patients.render_template', _boom)
        resp = client.get(f'/doctor/medical-history/{p.id}')
        _assert_redirect_to(resp, '/doctor/patient-queue')

    def test_prescriptions_history_outer_exception_redirects(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        _doctor_client(client, db, test_tenant)
        p = _patient(db)

        def _boom(*args, **kwargs):
            raise RuntimeError('render boom')

        monkeypatch.setattr('routes.doctor.patients.render_template', _boom)
        resp = client.get(f'/doctor/prescriptions-history/{p.id}')
        _assert_redirect_to(resp, '/doctor/patient-queue')

    def test_print_medical_report_missing_visit_redirects(
        self, app, client, db, test_tenant, rollback_db
    ):
        _doctor_client(client, db, test_tenant)
        resp = client.get('/doctor/print-medical-report/99999999')
        _assert_redirect_to(resp, '/doctor/patient-queue')

    def test_print_medical_report_outer_exception_redirects(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        def _boom(payload):
            raise RuntimeError('qr boom')

        monkeypatch.setattr('app.shared.print_context.generate_qr_data_uri', _boom)
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='COMPLETED')
        resp = client.get(f'/doctor/print-medical-report/{v.id}')
        _assert_redirect_to(resp, '/doctor/patient-queue')

    def test_patients_search_outer_exception_redirects(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        _doctor_client(client, db, test_tenant)

        def _boom(*args, **kwargs):
            raise RuntimeError('render boom')

        monkeypatch.setattr('routes.doctor.patients.render_template', _boom)
        resp = client.get('/doctor/patients')
        _assert_redirect_to(resp, '/doctor/patient-queue')

    def test_patient_timeline_outer_exception_redirects(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        _doctor_client(client, db, test_tenant)
        p = _patient(db)

        def _boom(*args, **kwargs):
            raise RuntimeError('timeline boom')

        monkeypatch.setattr(
            'services.patient_timeline_service.PatientTimelineService.build_events', _boom
        )
        resp = client.get(f'/doctor/patient-timeline/{p.id}')
        _assert_redirect_to(resp, '/doctor/patients')


class TestNotesGaps:
    def test_notes_audit_failure_still_saves_note(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')

        def _boom(*args, **kwargs):
            raise RuntimeError('audit boom')

        monkeypatch.setattr('routes.doctor.notes.AuditTrail', _boom)
        resp = client.post(f'/doctor/notes/{v.id}', data={'medical_notes': 'audit-survives-zzz'})
        _assert_redirect_to(resp, '/doctor/patient-queue')
        db.session.expire_all()
        assert 'audit-survives-zzz' in (db.session.get(Visit, v.id).notes or '')

    def test_notes_outer_exception_non_testing_redirects(
        self, app, client, db, test_tenant, rollback_db, monkeypatch
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        v = _visit(db, p, doc, _department(db), status='IN_PROGRESS')

        monkeypatch.setitem(app.config, 'TESTING', False)

        def _boom(*args, **kwargs):
            raise RuntimeError('render boom')

        monkeypatch.setattr('routes.doctor.notes.render_template', _boom)
        resp = client.get(f'/doctor/notes/{v.id}')
        _assert_redirect_to(resp, '/doctor/patient-queue')

    def test_note_templates_api_skips_non_dict_entries(
        self, app, client, db, test_tenant, rollback_db
    ):
        from models.system_config import SystemConfig

        _doctor_client(client, db, test_tenant)
        db.session.execute(
            delete(SystemConfig).filter_by(
                config_key='doctor_note_templates', tenant_id=test_tenant.id
            )
        )
        db.session.commit()
        db.session.add(
            SystemConfig(
                config_key='doctor_note_templates',
                tenant_id=test_tenant.id,
                config_type='json',
                config_value=json.dumps(
                    [
                        {'id': 'real-tpl', 'name': 'real', 'text': 'ok', 'is_active': True},
                        'not-a-dict-entry',
                        42,
                    ]
                ),
                category='general',
                description='test cfg',
                is_system=False,
                is_encrypted=False,
            )
        )
        db.session.commit()
        resp = client.get('/doctor/api/note-templates')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        ids = [t['id'] for t in body['templates']]
        assert 'real-tpl' in ids
        assert all(isinstance(t, dict) for t in body['templates'])

    def test_upsert_note_template_form_encoded_string_is_active(
        self, app, client, db, test_tenant, rollback_db
    ):
        _doctor_client(client, db, test_tenant)
        resp = client.post(
            '/doctor/api/note-templates',
            data={'name': f'form-tpl-{_tag()}', 'text': 'form text', 'is_active': 'yes'},
        )
        assert resp.status_code == 201
        template_id = resp.get_json()['id']
        resp = client.get('/doctor/api/note-templates?active_only=true')
        assert any(t['id'] == template_id for t in resp.get_json()['templates'])

    def test_upsert_note_template_rejects_when_fifty_exist(
        self, app, client, db, test_tenant, rollback_db
    ):
        from models.system_config import SystemConfig

        _doctor_client(client, db, test_tenant)
        db.session.execute(
            delete(SystemConfig).filter_by(
                config_key='doctor_note_templates', tenant_id=test_tenant.id
            )
        )
        templates = [
            {'id': f'filler-{i}', 'name': f'filler-{i}', 'text': 't', 'is_active': True}
            for i in range(50)
        ]
        db.session.add(
            SystemConfig(
                config_key='doctor_note_templates',
                tenant_id=test_tenant.id,
                config_type='json',
                config_value=json.dumps(templates),
                category='general',
                description='test cfg',
                is_system=False,
                is_encrypted=False,
            )
        )
        db.session.commit()
        resp = client.post(
            '/doctor/api/note-templates', json={'name': f'one-too-many-{_tag()}', 'text': 't'}
        )
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False


class TestDoctorPackageHelpers:
    def test_note_templates_reseed_when_config_holds_non_list(
        self, app, db, test_tenant, rollback_db
    ):
        from models.system_config import SystemConfig
        from routes.doctor import _get_doctor_note_templates

        doc = _make_doctor(db, test_tenant)
        db.session.execute(
            delete(SystemConfig).filter_by(
                config_key='doctor_note_templates', tenant_id=test_tenant.id
            )
        )
        db.session.add(
            SystemConfig(
                config_key='doctor_note_templates',
                tenant_id=test_tenant.id,
                config_type='json',
                config_value='{"not": "a list"}',
                category='general',
                description='test cfg',
                is_system=False,
                is_encrypted=False,
            )
        )
        db.session.commit()
        with _bound_request(app, test_tenant, doc):
            templates = _get_doctor_note_templates()
        assert isinstance(templates, list)
        assert len(templates) >= 1
        assert all('name' in t for t in templates)

    def test_note_templates_first_seed_commit_failure_raises(
        self, app, db, test_tenant, rollback_db, monkeypatch
    ):
        from models.system_config import SystemConfig
        from routes.doctor import _get_doctor_note_templates

        doc = _make_doctor(db, test_tenant)
        db.session.execute(
            delete(SystemConfig).filter_by(
                config_key='doctor_note_templates', tenant_id=test_tenant.id
            )
        )
        db.session.commit()

        def _boom(*args, **kwargs):
            raise RuntimeError('commit boom')

        monkeypatch.setattr('routes.doctor.safe_commit', _boom)
        with _bound_request(app, test_tenant, doc):
            with pytest.raises(RuntimeError, match='commit boom'):
                _get_doctor_note_templates()

    def test_save_note_templates_creates_missing_config(self, app, db, test_tenant, rollback_db):
        from models.system_config import SystemConfig
        from routes.doctor import _save_doctor_note_templates

        doc = _make_doctor(db, test_tenant)
        db.session.execute(
            delete(SystemConfig).filter_by(
                config_key='doctor_note_templates', tenant_id=test_tenant.id
            )
        )
        db.session.commit()
        with _bound_request(app, test_tenant, doc):
            _save_doctor_note_templates(
                [{'id': 'x1', 'name': 'one', 'text': 't', 'is_active': True}]
            )
        cfg = (
            db.session.execute(
                select(SystemConfig).filter_by(
                    config_key='doctor_note_templates', tenant_id=test_tenant.id
                )
            )
            .scalars()
            .first()
        )
        assert cfg is not None
        assert any(t['id'] == 'x1' for t in cfg.get_value())

    def test_save_note_templates_accepts_non_list_input(self, app, db, test_tenant, rollback_db):
        from models.system_config import SystemConfig
        from routes.doctor import _save_doctor_note_templates

        doc = _make_doctor(db, test_tenant)
        db.session.execute(
            delete(SystemConfig).filter_by(
                config_key='doctor_note_templates', tenant_id=test_tenant.id
            )
        )
        db.session.commit()
        with _bound_request(app, test_tenant, doc):
            _save_doctor_note_templates('not-a-list')
        cfg = (
            db.session.execute(
                select(SystemConfig).filter_by(
                    config_key='doctor_note_templates', tenant_id=test_tenant.id
                )
            )
            .scalars()
            .first()
        )
        assert cfg is not None
        assert cfg.get_value() == []

    def test_save_note_templates_commit_failure_raises(
        self, app, db, test_tenant, rollback_db, monkeypatch
    ):
        from routes.doctor import _save_doctor_note_templates

        doc = _make_doctor(db, test_tenant)

        def _boom(*args, **kwargs):
            raise RuntimeError('commit boom')

        monkeypatch.setattr('routes.doctor.safe_commit', _boom)
        with _bound_request(app, test_tenant, doc):
            with pytest.raises(RuntimeError, match='commit boom'):
                _save_doctor_note_templates([{'id': 'y', 'name': 'n', 'text': 't'}])

    def test_dashboard_layout_reseed_when_config_empty(self, app, db, test_tenant, rollback_db):
        from models.system_config import SystemConfig
        from routes.doctor import _get_doctor_dashboard_layout

        doc = _make_doctor(db, test_tenant)
        db.session.add(
            SystemConfig(
                config_key=f'doctor_dashboard_layout_{doc.id}',
                tenant_id=test_tenant.id,
                config_type='json',
                config_value='[]',
                category='general',
                description='test cfg',
                is_system=False,
                is_encrypted=False,
            )
        )
        db.session.commit()
        with _bound_request(app, test_tenant, doc):
            layout = _get_doctor_dashboard_layout()
        assert {item['id'] for item in layout} == {
            'stats_overview',
            'patients_actions',
            'smart_insights',
        }

    def test_dashboard_layout_first_seed_commit_failure_raises(
        self, app, db, test_tenant, rollback_db, monkeypatch
    ):
        from models.system_config import SystemConfig
        from routes.doctor import _get_doctor_dashboard_layout

        doc = _make_doctor(db, test_tenant)
        db.session.execute(
            delete(SystemConfig).filter_by(
                config_key=f'doctor_dashboard_layout_{doc.id}', tenant_id=test_tenant.id
            )
        )
        db.session.commit()

        def _boom(*args, **kwargs):
            raise RuntimeError('commit boom')

        monkeypatch.setattr('routes.doctor.safe_commit', _boom)
        with _bound_request(app, test_tenant, doc):
            with pytest.raises(RuntimeError, match='commit boom'):
                _get_doctor_dashboard_layout()

    def test_save_dashboard_layout_commit_failure_raises(
        self, app, db, test_tenant, rollback_db, monkeypatch
    ):
        from routes.doctor import _save_doctor_dashboard_layout

        doc = _make_doctor(db, test_tenant)

        def _boom(*args, **kwargs):
            raise RuntimeError('commit boom')

        monkeypatch.setattr('routes.doctor.safe_commit', _boom)
        with _bound_request(app, test_tenant, doc):
            with pytest.raises(RuntimeError, match='commit boom'):
                _save_doctor_dashboard_layout(
                    [{'id': 'stats_overview', 'title': 'x', 'order': 1, 'enabled': True}]
                )
