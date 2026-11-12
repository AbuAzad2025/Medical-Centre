"""HTTP-level coverage tests for the doctor blueprint (routes/doctor/*.py).

These tests exercise the real routes end to end against the test database:
requests are made with an authenticated doctor session, follow-ups are
asserted against actual database state, and wrong-role callers are checked
for 403 responses.

Fixtures come from tests/conftest.py (``app``, ``client``, ``db``,
``test_tenant``, ``rollback_db``); creation of tenant-scoped rows relies on
the same savepoint-isolated connection, so nothing here leaks into the
shared test database.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.shared.enums import LabResultStatus, VisitState
from models.appointment import Appointment
from models.audit_trail import AuditTrail
from models.dental import DentalChart, DentalTooth
from models.department import Department
from models.drug_interaction import DrugInteraction
from models.follow_up import FollowUpRequest
from models.invoice import Invoice
from models.lab_request import LabRequest, LabResult
from models.medical_record import MedicalRecord
from models.medication import Medication, Prescription
from models.notification import Notification
from models.patient import Patient, PatientAllergy
from models.queue_management import QueueManagement
from models.radiology_request import RadiologyRequest
from models.visit import Visit
from tests.tenant_context import ensure_test_user, login_test_client

_DOCTOR_USER = 'doccov_doctor'
_NURSE_USER = 'doccov_nurse'
_MANAGER_USER = 'doccov_manager'
_ADMIN_USER = 'doccov_admin'
_PHARMACIST_USER = 'doccov_pharmacist'
_RECEPTION_USER = 'doccov_reception'


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
        name_ar=name or ('الاستقبال' if reception else f'عيادة-{tag}'),
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


def _medication(db, *, trade_name=None, price='10.00', generic_name=None):
    med = Medication(
        scientific_name=generic_name or f'Scimed-{_tag()}',
        trade_name=trade_name or f'Ted-{_tag()}',
        generic_name=generic_name,
        dosage_form='tablet',
        strength='500mg',
        price=price,
        is_active=True,
    )
    db.session.add(med)
    db.session.commit()
    return med


def _expire(db):
    db.session.expire_all()


def _doctor_client(client, db, tenant):
    doc = _make_doctor(db, tenant)
    _login_as(client, db, tenant, doc)
    return doc


def _assert_redirect_to(resp, fragment: str):
    assert resp.status_code == 302
    assert fragment in resp.headers.get('Location', '')


# ---------------------------------------------------------------------------
# Dashboard surface
# ---------------------------------------------------------------------------


class TestDoctorDashboard:
    def test_dashboard_index_redirects(self, app, client, db, test_tenant, rollback_db):
        _doctor_client(client, db, test_tenant)
        resp = client.get('/doctor/')
        _assert_redirect_to(resp, '/doctor/dashboard')

    def test_dashboard_renders(self, app, client, db, test_tenant, rollback_db):
        _doctor_client(client, db, test_tenant)
        resp = client.get('/doctor/dashboard')
        assert resp.status_code == 200

    def test_dashboard_new_renders(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        _visit(db, p, doc, d, status='OPEN')
        resp = client.get('/doctor/dashboard-new')
        assert resp.status_code == 200

    def test_dashboard_for_doctor_manager_view(self, app, client, db, test_tenant, rollback_db):
        doc = _make_doctor(db, test_tenant, username=f'{_DOCTOR_USER}_target_{_tag()}')
        p = _patient(db)
        d = _department(db)
        _visit(db, p, doc, d, status='COMPLETED', total_amount=100)
        mgr = _make_doctor(db, test_tenant, role='manager', username=f'{_MANAGER_USER}_{_tag()}')
        _login_as(client, db, test_tenant, mgr)
        resp = client.get(f'/doctor/dashboard/{doc.id}')
        assert resp.status_code == 200

    def test_dashboard_for_doctor_forbidden_for_plain_doctor(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        resp = client.get(f'/doctor/dashboard/{doc.id}')
        assert resp.status_code == 403

    def test_dashboard_for_missing_doctor_redirects(
        self, app, client, db, test_tenant, rollback_db
    ):
        mgr = _make_doctor(db, test_tenant, role='manager', username=f'{_MANAGER_USER}_{_tag()}')
        _login_as(client, db, test_tenant, mgr)
        resp = client.get('/doctor/dashboard/99999999')
        assert resp.status_code == 302

    def test_api_dashboard_stats_exact_counts(self, app, client, db, test_tenant):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        _visit(db, p, doc, d, status='OPEN')
        _visit(db, p, doc, d, status='OPEN')
        _visit(db, p, doc, d, status='IN_PROGRESS')
        _visit(db, p, doc, d, status='COMPLETED')
        rx_visit = _visit(db, p, doc, d, status='IN_PROGRESS')
        med = _medication(db)

        from services.prescription_service import prescription_service

        ok, _rx = prescription_service.create_prescription(
            patient_id=p.id,
            doctor_id=doc.id,
            visit_id=rx_visit.id,
            tenant_id=test_tenant.id,
            items=[
                {
                    'medication_id': med.id,
                    'dosage': '500mg | مرة يومياً',
                    'quantity': 2,
                    'duration_days': 3,
                    'instructions': None,
                }
            ],
            prescription_number=f'RX-COV-{_tag()}',
        )
        assert ok

        db.session.add(
            Appointment(
                patient_id=p.id,
                doctor_id=doc.id,
                department_id=d.id,
                starts_at=datetime.now(UTC) + timedelta(hours=1),
                status='SCHEDULED',
            )
        )
        db.session.add(
            LabRequest(
                patient_id=p.id, visit_id=rx_visit.id, status='REQUESTED', requested_by=doc.id
            )
        )
        db.session.add(
            RadiologyRequest(
                patient_id=p.id, visit_id=rx_visit.id, status='REQUESTED', requested_by=doc.id
            )
        )
        db.session.commit()

        resp = client.get('/doctor/api/dashboard-stats')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        stats = body['stats']
        # 4 visits today for this doctor (3 OPEN-ish + 1 completed + rx visit)
        assert stats['today_visits'] == 5
        assert stats['waiting_patients'] == 2
        assert stats['in_progress'] == 2
        assert stats['completed_today'] == 1
        assert stats['prescriptions_today'] == 1
        assert stats['appointments_today'] == 1
        assert stats['pending_lab'] == 1
        assert stats['pending_radiology'] == 1
        assert 'timestamp' in stats

    def test_api_dashboard_stats_wrong_role_403(self, app, client, db, test_tenant, rollback_db):
        nurse = _make_doctor(db, test_tenant, role='nurse', username=f'{_NURSE_USER}_{_tag()}')
        _login_as(client, db, test_tenant, nurse)
        resp = client.get('/doctor/api/dashboard-stats', headers={'Accept': 'application/json'})
        assert resp.status_code == 403

    def test_api_today_visits_lists_open_and_in_progress_only(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db, first_name='Todaycheck', last_name='Person')
        d = _department(db)
        v_open = _visit(db, p, doc, d, status='OPEN')
        v_progress = _visit(db, p, doc, d, status='IN_PROGRESS')
        _visit(db, p, doc, d, status='COMPLETED')

        resp = client.get('/doctor/api/today-visits')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        ids = [v['id'] for v in body['visits']]
        assert v_open.id in ids
        assert v_progress.id in ids
        assert len(body['visits']) == 2
        row = next(v for v in body['visits'] if v['id'] == v_open.id)
        assert row['patient_name'] == p.full_name
        assert row['status_label'] == 'OPEN'
        assert f'/doctor/patient-details/{v_open.id}' in row['details_url']

    def test_api_today_visits_wrong_role_403(self, app, client, db, test_tenant, rollback_db):
        pharm = _make_doctor(
            db, test_tenant, role='pharmacist', username=f'{_PHARMACIST_USER}_{_tag()}'
        )
        _login_as(client, db, test_tenant, pharm)
        resp = client.get('/doctor/api/today-visits', headers={'Accept': 'application/json'})
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Visits surface (queue lifecycle, details, summary)
# ---------------------------------------------------------------------------


class TestVisitsFlow:
    def test_full_call_start_complete_flow(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='OPEN')
        t = _tick(db, v, d, status='waiting')

        resp = client.post(f'/doctor/call-patient/{v.id}')
        _assert_redirect_to(resp, '/doctor/patient-queue')
        db.session.expire_all()
        ticket = db.session.get(QueueManagement, t.id)
        assert ticket.status == 'called'
        assert ticket.called_at is not None

        resp = client.post(f'/doctor/start-treatment/{v.id}')
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        db.session.expire_all()
        assert db.session.get(Visit, v.id).status == VisitState.IN_PROGRESS.value
        assert db.session.get(QueueManagement, t.id).status == 'in_progress'
        record = (
            db.session.execute(select(MedicalRecord).filter_by(visit_id=v.id, title='بدء العلاج'))
            .scalars()
            .first()
        )
        assert record is not None
        start_audits = (
            db.session.execute(select(AuditTrail).filter_by(entity_type='visit', entity_id=v.id))
            .scalars()
            .all()
        )
        assert any(a.description == 'بدء علاج المريض' for a in start_audits)

        resp = client.post(f'/doctor/end-treatment/{v.id}')
        _assert_redirect_to(resp, '/doctor/patient-queue')
        db.session.expire_all()
        done = db.session.get(Visit, v.id)
        assert done.status == VisitState.COMPLETED.value
        assert done.completed_by == doc.id
        assert done.completed_at is not None
        assert db.session.get(QueueManagement, t.id).status == 'completed'
        end_record = (
            db.session.execute(select(MedicalRecord).filter_by(visit_id=v.id, title='إنهاء العلاج'))
            .scalars()
            .first()
        )
        assert end_record is not None
        end_audits = (
            db.session.execute(select(AuditTrail).filter_by(entity_type='visit', entity_id=v.id))
            .scalars()
            .all()
        )
        assert any(a.description == 'إنهاء العلاج' for a in end_audits)

    def test_start_treatment_without_queue_ticket_warns(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='OPEN')
        resp = client.post(f'/doctor/start-treatment/{v.id}', follow_redirects=True)
        assert resp.status_code == 200
        db.session.expire_all()
        assert db.session.get(Visit, v.id).status == VisitState.OPEN.value

    def test_start_treatment_requires_called_ticket(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='OPEN')
        _tick(db, v, d, status='waiting')
        resp = client.post(f'/doctor/start-treatment/{v.id}', follow_redirects=True)
        assert resp.status_code == 200
        db.session.expire_all()
        assert db.session.get(Visit, v.id).status == VisitState.OPEN.value

    def test_end_treatment_rejects_non_in_progress_visit(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='OPEN')
        resp = client.post(f'/doctor/end-treatment/{v.id}', follow_redirects=True)
        assert resp.status_code == 200
        db.session.expire_all()
        assert db.session.get(Visit, v.id).status == VisitState.OPEN.value

    def test_end_treatment_completes_visit_without_ticket(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        resp = client.post(f'/doctor/end-treatment/{v.id}')
        _assert_redirect_to(resp, '/doctor/patient-queue')
        db.session.expire_all()
        assert db.session.get(Visit, v.id).status == VisitState.COMPLETED.value

    def test_start_treatment_other_doctors_visit_redirects(
        self, app, client, db, test_tenant, rollback_db
    ):
        owner = _make_doctor(db, test_tenant, username=f'{_DOCTOR_USER}_owner_{_tag()}')
        _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, owner, d, status='OPEN')
        resp = client.post(f'/doctor/start-treatment/{v.id}')
        _assert_redirect_to(resp, '/doctor/patient-queue')
        db.session.expire_all()
        assert db.session.get(Visit, v.id).status == VisitState.OPEN.value

    def test_end_treatment_wrong_role_403(self, app, client, db, test_tenant, rollback_db):
        nurse = _make_doctor(db, test_tenant, role='nurse', username=f'{_NURSE_USER}_{_tag()}')
        _login_as(client, db, test_tenant, nurse)
        doc = _make_doctor(db, test_tenant, username=f'{_DOCTOR_USER}_z_{_tag()}')
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        resp = client.post(f'/doctor/end-treatment/{v.id}')
        assert resp.status_code == 403

    def test_visits_list_redirects_to_queue(self, app, client, db, test_tenant, rollback_db):
        _doctor_client(client, db, test_tenant)
        resp = client.get('/doctor/visits')
        _assert_redirect_to(resp, '/doctor/patient-queue')

    def test_view_patient_redirects_to_details(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d)
        resp = client.get(f'/doctor/view_patient/{v.id}')
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')

    def test_patient_details_renders(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db, first_name='Detailscheck', last_name='Person')
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        resp = client.get(f'/doctor/patient-details/{v.id}')
        assert resp.status_code == 200
        assert 'Detailscheck' in resp.get_data(as_text=True)

    def test_patient_details_missing_visit_redirects(
        self, app, client, db, test_tenant, rollback_db
    ):
        _doctor_client(client, db, test_tenant)
        resp = client.get('/doctor/patient-details/99999999')
        _assert_redirect_to(resp, '/doctor/patient-queue')

    def test_patient_details_other_doctors_visit_redirects(
        self, app, client, db, test_tenant, rollback_db
    ):
        owner = _make_doctor(db, test_tenant, username=f'{_DOCTOR_USER}_owner_{_tag()}')
        _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, owner, d)
        resp = client.get(f'/doctor/patient-details/{v.id}')
        _assert_redirect_to(resp, '/doctor/patient-queue')


class TestVisitSummary:
    def test_visit_summary_renders_for_owned_visit(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='COMPLETED')
        resp = client.get(f'/doctor/visit-summary/{v.id}')
        assert resp.status_code == 200

    def test_visit_summary_missing_visit_redirects(self, app, client, db, test_tenant, rollback_db):
        _doctor_client(client, db, test_tenant)
        resp = client.get('/doctor/visit-summary/99999999')
        _assert_redirect_to(resp, '/doctor/patient-queue')

    def test_save_visit_summary_requires_in_progress_or_completed(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='OPEN')
        resp = client.post(f'/doctor/save-visit-summary/{v.id}', json={'diagnosis': 'x'})
        assert resp.status_code == 400
        assert resp.get_json()['success'] is False

    def test_save_visit_summary_missing_visit_404(self, app, client, db, test_tenant, rollback_db):
        _doctor_client(client, db, test_tenant)
        resp = client.post('/doctor/save-visit-summary/99999999', json={'diagnosis': 'x'})
        assert resp.status_code == 404
        assert resp.get_json()['success'] is False

    def test_save_visit_summary_updates_visit_and_notes(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        resp = client.post(
            f'/doctor/save-visit-summary/{v.id}',
            json={
                'diagnosis': 'التهاب الحلق',
                'treatment_plan': 'غرغرة ومسكنات',
                'chief_complaint': 'ألم في الحلق',
                'history_of_present_illness': 'بدأ منذ يومين',
                'recommendations': 'راحة وشرب الماء',
                'follow_up_date': '2026-12-15',
                'follow_up_notes': 'مراجعة بعد أسبوعين',
            },
        )
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True
        db.session.expire_all()
        v2 = db.session.get(Visit, v.id)
        assert v2.diagnosis == 'التهاب الحلق'
        assert v2.treatment_plan == 'غرغرة ومسكنات'
        assert v2.symptoms == 'ألم في الحلق'
        assert v2.follow_up_date == date(2026, 12, 15)
        assert v2.follow_up_required is True
        assert 'تاريخ المرض الحالي' in (v2.notes or '')
        assert 'التوصيات' in (v2.notes or '')
        assert 'ملاحظات المتابعة' in (v2.notes or '')

    def test_save_visit_summary_form_encoded(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='COMPLETED')
        resp = client.post(
            f'/doctor/save-visit-summary/{v.id}',
            data={'diagnosis': 'صداع', 'treatment_plan': 'راحة'},
        )
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True
        db.session.expire_all()
        assert db.session.get(Visit, v.id).diagnosis == 'صداع'

    def test_save_visit_summary_invalid_follow_up_date_still_succeeds(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        resp = client.post(
            f'/doctor/save-visit-summary/{v.id}',
            json={'diagnosis': 'x', 'follow_up_date': 'not-a-date'},
        )
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True
        db.session.expire_all()
        v2 = db.session.get(Visit, v.id)
        assert v2.follow_up_date is None

    def test_save_visit_summary_wrong_role_403(self, app, client, db, test_tenant, rollback_db):
        nurse = _make_doctor(db, test_tenant, role='nurse', username=f'{_NURSE_USER}_{_tag()}')
        _login_as(client, db, test_tenant, nurse)
        doc = _make_doctor(db, test_tenant, username=f'{_DOCTOR_USER}_w_{_tag()}')
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        resp = client.post(f'/doctor/save-visit-summary/{v.id}', json={'diagnosis': 'x'})
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Diagnosis surface
# ---------------------------------------------------------------------------


def _diagnosis_post(visit_id, **overrides):
    data = {
        'chief_complaint': 'صداع متكرر',
        'symptoms': 'صداع نابض',
        'diagnosis': 'صداع نصفي',
        'differential_diagnosis': 'صداع توتري',
        'treatment_plan': 'مسكنات ومتابعة',
        'follow_up_notes': 'مراجعة بعد أسبوع',
        'follow_up_date': '2026-12-20',
        'blood_pressure': '118/76',
        'heart_rate': '72',
        'temperature': '36.8',
        'respiratory_rate': '16',
        'notes': 'ملاحظات الطبيب',
    }
    data.update(overrides)
    return data


class TestDiagnosisGet:
    def test_diagnosis_page_renders(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, vital_signs='{"blood_pressure": "118/76"}')
        resp = client.get(f'/doctor/diagnosis/{v.id}')
        assert resp.status_code == 200
        assert '118/76' in resp.get_data(as_text=True)

    def test_diagnosis_page_parses_python_dict_vital_signs(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, vital_signs="{'blood_pressure': '110/70', 'heart_rate': '65'}")
        resp = client.get(f'/doctor/diagnosis/{v.id}')
        assert resp.status_code == 200
        assert '110/70' in resp.get_data(as_text=True)

    def test_diagnosis_page_tolerates_malformed_vital_signs(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, vital_signs='not-json-and-not-literal')
        resp = client.get(f'/doctor/diagnosis/{v.id}')
        assert resp.status_code == 200

    def test_diagnosis_page_blocked_when_completed(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='COMPLETED')
        resp = client.get(f'/doctor/diagnosis/{v.id}')
        _assert_redirect_to(resp, '/doctor/patient-queue')

    def test_diagnosis_page_blocked_when_archived(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, archive_status='ARCHIVED')
        resp = client.get(f'/doctor/diagnosis/{v.id}')
        _assert_redirect_to(resp, '/doctor/patient-queue')

    def test_diagnosis_page_other_doctors_visit_redirects(
        self, app, client, db, test_tenant, rollback_db
    ):
        owner = _make_doctor(db, test_tenant, username=f'{_DOCTOR_USER}_dx_{_tag()}')
        _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, owner, d)
        resp = client.get(f'/doctor/diagnosis/{v.id}')
        _assert_redirect_to(resp, '/doctor/patient-queue')


class TestDiagnosisPost:
    def test_save_diagnosis_writes_visit_record_audit_and_follow_up(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='OPEN')

        resp = client.post(
            f'/doctor/diagnosis/{v.id}',
            data=_diagnosis_post(v.id, follow_up_required='on'),
        )
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')

        db.session.expire_all()
        v2 = db.session.get(Visit, v.id)
        assert v2.chief_complaint == 'صداع متكرر'
        assert v2.symptoms == 'صداع نابض'
        assert v2.diagnosis == 'صداع نصفي'
        assert v2.differential_diagnosis == 'صداع توتري'
        assert v2.treatment_plan == 'مسكنات ومتابعة'
        assert v2.follow_up_notes == 'مراجعة بعد أسبوع'
        assert v2.follow_up_date == date(2026, 12, 20)
        assert v2.follow_up_required is True
        # The visit was still OPEN; the state machine moves it to IN_PROGRESS.
        assert v2.status == VisitState.IN_PROGRESS.value
        vitals = json.loads(v2.vital_signs)
        assert vitals['blood_pressure'] == '118/76'
        assert vitals['heart_rate'] == '72'
        assert vitals['temperature'] == '36.8'
        assert vitals['respiratory_rate'] == '16'
        assert 'ملاحظات الطبيب' in (v2.notes or '')

        records = (
            db.session.execute(select(MedicalRecord).filter_by(visit_id=v.id, title='تشخيص طبي'))
            .scalars()
            .all()
        )
        assert len(records) == 1

        audits = (
            db.session.execute(select(AuditTrail).filter_by(entity_type='visit', entity_id=v.id))
            .scalars()
            .all()
        )
        assert any(a.description == 'حفظ التشخيص' for a in audits)

        follow_ups = (
            db.session.execute(select(FollowUpRequest).filter_by(source_visit_id=v.id))
            .scalars()
            .all()
        )
        assert len(follow_ups) == 1
        assert follow_ups[0].status == 'PENDING'
        assert follow_ups[0].suggested_date == date(2026, 12, 20)
        assert follow_ups[0].patient_id == p.id
        assert follow_ups[0].doctor_id == doc.id

    def test_save_diagnosis_merges_vital_signs_instead_of_replacing(
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
            vital_signs='{"blood_pressure": "111/71", "heart_rate": "60"}',
        )
        resp = client.post(
            f'/doctor/diagnosis/{v.id}',
            data=_diagnosis_post(
                v.id,
                blood_pressure='',
                heart_rate='',
                temperature='37.2',
                respiratory_rate='',
                follow_up_date='',
            ),
        )
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        db.session.expire_all()
        vitals = json.loads(db.session.get(Visit, v.id).vital_signs)
        assert vitals['blood_pressure'] == '111/71'
        assert vitals['heart_rate'] == '60'
        assert vitals['temperature'] == '37.2'

    def test_resave_does_not_duplicate_memo_or_medical_record(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')

        for _ in range(2):
            resp = client.post(
                f'/doctor/diagnosis/{v.id}',
                data=_diagnosis_post(
                    v.id, notes='نفس الملاحظة', follow_up_date='', follow_up_required=''
                ),
            )
            _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')

        db.session.expire_all()
        v2 = db.session.get(Visit, v.id)
        assert (v2.notes or '').count('نفس الملاحظة') == 1
        records = (
            db.session.execute(select(MedicalRecord).filter_by(visit_id=v.id, title='تشخيص طبي'))
            .scalars()
            .all()
        )
        assert len(records) == 1

    def test_follow_up_cancelled_on_resave_without_requirement(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')

        resp = client.post(
            f'/doctor/diagnosis/{v.id}',
            data=_diagnosis_post(v.id, follow_up_required='on'),
        )
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        resp = client.post(
            f'/doctor/diagnosis/{v.id}',
            data=_diagnosis_post(v.id, follow_up_required='', follow_up_date=''),
        )
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')

        follow_ups = (
            db.session.execute(select(FollowUpRequest).filter_by(source_visit_id=v.id))
            .scalars()
            .all()
        )
        assert len(follow_ups) == 1
        assert follow_ups[0].status == 'CANCELLED'

    def test_oversized_chief_complaint_rejected(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        resp = client.post(
            f'/doctor/diagnosis/{v.id}',
            data=_diagnosis_post(v.id, chief_complaint='x' * 2001, follow_up_date=''),
        )
        _assert_redirect_to(resp, f'/doctor/diagnosis/{v.id}')
        db.session.expire_all()
        v2 = db.session.get(Visit, v.id)
        assert v2.chief_complaint is None

    def test_oversized_diagnosis_rejected(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        resp = client.post(
            f'/doctor/diagnosis/{v.id}',
            data=_diagnosis_post(v.id, diagnosis='x' * 2001, follow_up_date=''),
        )
        _assert_redirect_to(resp, f'/doctor/diagnosis/{v.id}')
        db.session.expire_all()
        assert db.session.get(Visit, v.id).diagnosis is None

    def test_oversized_notes_rejected(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        resp = client.post(
            f'/doctor/diagnosis/{v.id}',
            data=_diagnosis_post(v.id, notes='x' * 5001, follow_up_date=''),
        )
        _assert_redirect_to(resp, f'/doctor/diagnosis/{v.id}')
        db.session.expire_all()
        assert 'x' * 5001 not in (db.session.get(Visit, v.id).notes or '')

    def test_invalid_follow_up_date_keeps_existing_value(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS', follow_up_date=date(2026, 11, 30))
        resp = client.post(
            f'/doctor/diagnosis/{v.id}',
            data=_diagnosis_post(v.id, follow_up_date='31/12/2026'),
        )
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        db.session.expire_all()
        assert db.session.get(Visit, v.id).follow_up_date == date(2026, 11, 30)

    def test_post_blocked_when_completed(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='COMPLETED', diagnosis='الأصلي')
        resp = client.post(
            f'/doctor/diagnosis/{v.id}',
            data=_diagnosis_post(v.id, diagnosis='معدّل'),
        )
        _assert_redirect_to(resp, '/doctor/patient-queue')
        db.session.expire_all()
        assert db.session.get(Visit, v.id).diagnosis == 'الأصلي'

    def test_post_wrong_role_403(self, app, client, db, test_tenant, rollback_db):
        nurse = _make_doctor(db, test_tenant, role='nurse', username=f'{_NURSE_USER}_{_tag()}')
        _login_as(client, db, test_tenant, nurse)
        doc = _make_doctor(db, test_tenant, username=f'{_DOCTOR_USER}_v_{_tag()}')
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        resp = client.post(f'/doctor/diagnosis/{v.id}', data=_diagnosis_post(v.id))
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Prescriptions surface
# ---------------------------------------------------------------------------


def _rx_items_form(
    med_ids, dosages=None, frequencies=None, durations=None, quantities=None, instructions=None
):
    dosages = dosages or ['500mg'] * len(med_ids)
    frequencies = frequencies or ['مرتين يومياً'] * len(med_ids)
    durations = durations or ['7'] * len(med_ids)
    quantities = quantities or ['10'] * len(med_ids)
    instructions = instructions or ['بعد الطعام'] * len(med_ids)
    return {
        'item_medication_id[]': [str(m) for m in med_ids],
        'item_dosage[]': dosages,
        'item_frequency[]': frequencies,
        'item_duration_days[]': durations,
        'item_quantity[]': quantities,
        'item_instructions[]': instructions,
    }


class TestPrescriptionPage:
    def test_get_prescription_page_renders(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        resp = client.get(f'/doctor/prescription/{v.id}')
        assert resp.status_code == 200

    def test_get_prescription_page_requires_in_progress(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='OPEN')
        resp = client.get(f'/doctor/prescription/{v.id}')
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')

    def test_get_prescription_page_other_doctors_visit_redirects(
        self, app, client, db, test_tenant, rollback_db
    ):
        owner = _make_doctor(db, test_tenant, username=f'{_DOCTOR_USER}_rx_{_tag()}')
        _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, owner, d, status='IN_PROGRESS')
        resp = client.get(f'/doctor/prescription/{v.id}')
        _assert_redirect_to(resp, '/doctor/patient-queue')

    def test_post_prescription_forbidden_for_nurse(self, app, client, db, test_tenant, rollback_db):
        nurse = _make_doctor(db, test_tenant, role='nurse', username=f'{_NURSE_USER}_{_tag()}')
        _login_as(client, db, test_tenant, nurse)
        doc = _make_doctor(db, test_tenant, username=f'{_DOCTOR_USER}_a_{_tag()}')
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        resp = client.get(f'/doctor/prescription/{v.id}')
        assert resp.status_code == 403

    def test_post_without_items_rerenders_form(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        resp = client.post(f'/doctor/prescription/{v.id}', data={})
        assert resp.status_code == 200
        assert (
            db.session.execute(select(Prescription).filter_by(visit_id=v.id)).scalars().all() == []
        )


class TestPrescriptionCreate:
    def test_create_prescription_persists_items_and_flags(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS', diagnosis='نزلة برد')
        med = _medication(db, price='15.50')

        resp = client.post(
            f'/doctor/prescription/{v.id}',
            data=_rx_items_form([med.id], durations=['5'], quantities=['10']),
        )
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')

        rx = db.session.execute(select(Prescription).filter_by(visit_id=v.id)).scalars().first()
        assert rx is not None
        assert rx.doctor_id == doc.id
        assert rx.patient_id == p.id
        assert rx.prescription_number.startswith(f'RX-{v.id}-')
        assert rx.diagnosis == 'نزلة برد'
        items = rx.items.all()
        assert len(items) == 1
        item = items[0]
        assert item.medication_id == med.id
        assert item.dosage == '500mg | مرتين يومياً'
        assert item.quantity == 10
        assert item.duration_days == 5
        assert item.instructions == 'بعد الطعام'
        assert float(item.total_price) == 15.50 * 10

        db.session.expire_all()
        assert db.session.get(Visit, v.id).prescription_issued is True

        audits = (
            db.session.execute(select(AuditTrail).filter_by(entity_type='visit', entity_id=v.id))
            .scalars()
            .all()
        )
        assert any(a.description == 'إضافة وصفة طبية' for a in audits)

    def test_create_prescription_hands_off_to_reception_when_present(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        reception = _department(db, name='Reception', reception=True)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        med = _medication(db)

        resp = client.post(f'/doctor/prescription/{v.id}', data=_rx_items_form([med.id]))
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        db.session.expire_all()
        v2 = db.session.get(Visit, v.id)
        assert v2.department_id == reception.id
        assert v2.pending_financial_settlement is True

    def test_create_prescription_legacy_medication_lookup(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        med = _medication(db, trade_name='LegacyMed-XYZ', generic_name='legacygeneric')

        resp = client.post(
            f'/doctor/prescription/{v.id}',
            data={
                'medication_name': 'LegacyMed-XYZ',
                'dosage': '250mg',
                'frequency': 'ثلاث مرات يومياً',
                'duration': '7 days',
                'instructions': 'بعد الأكل',
            },
        )
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        rx = db.session.execute(select(Prescription).filter_by(visit_id=v.id)).scalars().first()
        assert rx is not None
        items = rx.items.all()
        assert len(items) == 1
        assert items[0].medication_id == med.id
        assert items[0].duration_days == 7

    def test_create_prescription_legacy_unknown_med_goes_to_non_catalog(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')

        resp = client.post(
            f'/doctor/prescription/{v.id}',
            data={'medication_name': 'NoSuchDrugAnywhere-QQ', 'dosage': '5mg'},
        )
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        rx = db.session.execute(select(Prescription).filter_by(visit_id=v.id)).scalars().first()
        assert rx is not None
        assert rx.items.count() == 0
        assert 'NoSuchDrugAnywhere-QQ' in (rx.notes or '')
        # The pharmacy was notified about the unknown medication.
        notif = (
            db.session.execute(select(Notification).filter_by(recipient_role='pharmacist'))
            .scalars()
            .all()
        )
        assert any('NoSuchDrugAnywhere-QQ' in (n.message or '') for n in notif)

    def test_allergy_hard_stop_blocks_prescription(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        db.session.add(PatientAllergy(patient_id=p.id, allergen='amoxicillin'))
        db.session.commit()
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        med = _medication(db, trade_name='Amx-Test', generic_name='amoxicillin')

        resp = client.post(
            f'/doctor/prescription/{v.id}',
            data=_rx_items_form([med.id]),
            headers={'X-Requested-With': 'XMLHttpRequest'},
        )
        assert resp.status_code == 422
        body = resp.get_json()
        assert body['success'] is False
        assert body['hard_stops']
        assert 'amoxicillin' in body['message'].lower()
        n_rx = (
            db.session.execute(
                select(func.count()).select_from(Prescription).filter_by(visit_id=v.id)
            )
        ).scalar()
        assert n_rx == 0

    def test_allergy_hard_stop_redirects_for_form_post(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        db.session.add(PatientAllergy(patient_id=p.id, allergen='amoxicillin'))
        db.session.commit()
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        med = _medication(db, trade_name='Amx-Test2', generic_name='amoxicillin')

        resp = client.post(f'/doctor/prescription/{v.id}', data=_rx_items_form([med.id]))
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        n_rx = (
            db.session.execute(
                select(func.count()).select_from(Prescription).filter_by(visit_id=v.id)
            )
        ).scalar()
        assert n_rx == 0

    def test_moderate_drug_interaction_saves_with_warning(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        med_a = _medication(db, trade_name='ModA-Warf')
        med_b = _medication(db, trade_name='ModB-Asp')
        lo, hi = sorted([med_a.id, med_b.id])
        db.session.add(
            DrugInteraction(
                medication_a_id=lo,
                medication_b_id=hi,
                severity='MODERATE',
                is_active=True,
                description='combined use needs monitoring',
            )
        )
        db.session.commit()

        resp = client.post(
            f'/doctor/prescription/{v.id}',
            data=_rx_items_form([med_a.id, med_b.id]),
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert 'تداخل دوائي' in resp.get_data(as_text=True)
        n_rx = (
            db.session.execute(
                select(func.count()).select_from(Prescription).filter_by(visit_id=v.id)
            )
        ).scalar()
        assert n_rx == 1

    def test_high_drug_interaction_blocks_prescription(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        med_a = _medication(db, trade_name='HighA-Warf')
        med_b = _medication(db, trade_name='HighB-Clari')
        lo, hi = sorted([med_a.id, med_b.id])
        db.session.add(
            DrugInteraction(
                medication_a_id=lo,
                medication_b_id=hi,
                severity='HIGH',
                is_active=True,
                description='major interaction',
            )
        )
        db.session.commit()

        resp = client.post(
            f'/doctor/prescription/{v.id}',
            data=_rx_items_form([med_a.id, med_b.id]),
        )
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        n_rx = (
            db.session.execute(
                select(func.count()).select_from(Prescription).filter_by(visit_id=v.id)
            )
        ).scalar()
        assert n_rx == 0

    def test_duplicate_therapy_against_active_prescription_warns_not_blocks(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        med = _medication(db, trade_name='DupRx-Med')
        # An existing active prescription already contains this drug.
        resp = client.post(f'/doctor/prescription/{v.id}', data=_rx_items_form([med.id]))
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        # Writing the same drug again: the duplicate-therapy check must warn,
        # not hard-stop. Before the medication_id fix the check raised
        # AttributeError, which surfaced as an "unable to verify" critical
        # alert and blocked the write entirely.
        resp = client.post(f'/doctor/prescription/{v.id}', data=_rx_items_form([med.id]))
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        n_rx = (
            db.session.execute(
                select(func.count()).select_from(Prescription).filter_by(visit_id=v.id)
            )
        ).scalar()
        assert n_rx == 2

    def test_save_as_template_persists_system_config(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        med = _medication(db, trade_name='Tpl-Med-1')

        data = _rx_items_form([med.id])
        data['save_as_template'] = 'on'
        data['template_name'] = 'قالبي الخاص'
        resp = client.post(f'/doctor/prescription/{v.id}', data=data)
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')

        from models.system_config import SystemConfig

        cfg = (
            db.session.execute(
                select(SystemConfig).filter_by(config_key=f'doctor_rx_templates_{doc.id}')
            )
            .scalars()
            .first()
        )
        assert cfg is not None
        templates = cfg.get_value()
        assert any(t.get('name') == 'قالبي الخاص' for t in templates)
        tpl = next(t for t in templates if t.get('name') == 'قالبي الخاص')
        assert tpl['items'][0]['medication_id'] == med.id


class TestPrintPrescription:
    def _rx_for(self, db, p, doc, v):
        rx = Prescription(
            patient_id=p.id,
            doctor_id=doc.id,
            visit_id=v.id,
            prescription_number=f'RX-PRINT-{_tag()}',
            status='active',
        )
        db.session.add(rx)
        db.session.commit()
        return rx

    def test_owner_can_print(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        rx = self._rx_for(db, p, doc, v)
        resp = client.get(f'/doctor/print-prescription/{rx.id}')
        assert resp.status_code == 200

    def test_other_doctor_cannot_print(self, app, client, db, test_tenant, rollback_db):
        owner = _make_doctor(db, test_tenant, username=f'{_DOCTOR_USER}_owner_{_tag()}')
        _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, owner, d, status='IN_PROGRESS')
        rx = self._rx_for(db, p, owner, v)
        resp = client.get(f'/doctor/print-prescription/{rx.id}')
        _assert_redirect_to(resp, '/doctor/patient-queue')

    def test_missing_prescription_redirects(self, app, client, db, test_tenant, rollback_db):
        _doctor_client(client, db, test_tenant)
        resp = client.get('/doctor/print-prescription/99999999')
        _assert_redirect_to(resp, '/doctor/patient-queue')


class TestPrescriptionsListAndPrint:
    def test_prescriptions_list_renders_own_items(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        med = _medication(db)
        resp = client.post(f'/doctor/prescription/{v.id}', data=_rx_items_form([med.id]))
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        rx = db.session.execute(select(Prescription).filter_by(visit_id=v.id)).scalars().first()
        assert rx is not None
        resp = client.get('/doctor/prescriptions')
        assert resp.status_code == 200
        assert rx.prescription_number in resp.get_data(as_text=True)

    def test_prescriptions_list_wrong_role_403(self, app, client, db, test_tenant, rollback_db):
        nurse = _make_doctor(db, test_tenant, role='nurse', username=f'{_NURSE_USER}_{_tag()}')
        _login_as(client, db, test_tenant, nurse)
        resp = client.get('/doctor/prescriptions')
        assert resp.status_code == 403

    def test_print_invoice_owner_only(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='COMPLETED', total_amount=120)
        inv = Invoice(visit_id=v.id, total_amount=120, paid_amount=0, status='ISSUED')
        db.session.add(inv)
        db.session.commit()
        resp = client.get(f'/doctor/print-invoice/{inv.id}')
        assert resp.status_code == 200

    def test_print_invoice_other_doctor_redirects(self, app, client, db, test_tenant, rollback_db):
        owner = _make_doctor(db, test_tenant, username=f'{_DOCTOR_USER}_inv_{_tag()}')
        _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, owner, d, status='COMPLETED', total_amount=120)
        inv = Invoice(visit_id=v.id, total_amount=120, paid_amount=0, status='ISSUED')
        db.session.add(inv)
        db.session.commit()
        resp = client.get(f'/doctor/print-invoice/{inv.id}')
        _assert_redirect_to(resp, '/doctor/patient-queue')

    def test_print_invoice_missing_redirects(self, app, client, db, test_tenant, rollback_db):
        _doctor_client(client, db, test_tenant)
        resp = client.get('/doctor/print-invoice/99999999')
        _assert_redirect_to(resp, '/doctor/patient-queue')

    def test_print_receipt_owner_only(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='COMPLETED', total_amount=75)
        resp = client.get(f'/doctor/print-receipt/{v.id}')
        assert resp.status_code == 200

    def test_print_receipt_other_doctor_redirects(self, app, client, db, test_tenant, rollback_db):
        owner = _make_doctor(db, test_tenant, username=f'{_DOCTOR_USER}_rcp_{_tag()}')
        _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, owner, d, status='COMPLETED', total_amount=75)
        resp = client.get(f'/doctor/print-receipt/{v.id}')
        _assert_redirect_to(resp, '/doctor/patient-queue')

    def test_print_medical_report_owner(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='COMPLETED')
        resp = client.get(f'/doctor/print-medical-report/{v.id}')
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Patient queue surface
# ---------------------------------------------------------------------------


class TestPatientQueue:
    def test_queue_lists_doctor_visits(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db, first_name='Queuecheck', last_name='Person')
        d = _department(db)
        v_open = _visit(db, p, doc, d, status='OPEN')
        _visit(db, p, doc, d, status='IN_PROGRESS')
        _visit(db, p, doc, d, status='COMPLETED')
        _tick(db, v_open, d, status='called')
        resp = client.get('/doctor/patient-queue')
        assert resp.status_code == 200
        body = resp.get_data(as_text=True)
        assert 'Queuecheck' in body
        assert f'/doctor/patient-details/{v_open.id}' in body

    def test_queue_wrong_role_403(self, app, client, db, test_tenant, rollback_db):
        nurse = _make_doctor(db, test_tenant, role='nurse', username=f'{_NURSE_USER}_{_tag()}')
        _login_as(client, db, test_tenant, nurse)
        resp = client.get('/doctor/patient-queue')
        assert resp.status_code == 403

    def test_call_patient_marks_waiting_ticket_called(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='OPEN')
        t = _tick(db, v, d, status='waiting')
        resp = client.post(f'/doctor/call-patient/{v.id}')
        _assert_redirect_to(resp, '/doctor/patient-queue')
        db.session.expire_all()
        t2 = db.session.get(QueueManagement, t.id)
        assert t2.status == 'called'
        assert t2.called_at is not None

    def test_call_patient_without_ticket_warns(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='OPEN')
        resp = client.post(f'/doctor/call-patient/{v.id}', follow_redirects=True)
        assert resp.status_code == 200
        assert (
            db.session.execute(
                select(func.count()).select_from(QueueManagement).filter_by(visit_id=v.id)
            ).scalar()
            == 0
        )

    def test_call_patient_when_already_called_warns(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='OPEN')
        t = _tick(db, v, d, status='called')
        resp = client.post(f'/doctor/call-patient/{v.id}', follow_redirects=True)
        assert resp.status_code == 200
        db.session.expire_all()
        assert db.session.get(QueueManagement, t.id).status == 'called'

    def test_call_patient_other_doctors_visit_redirects(
        self, app, client, db, test_tenant, rollback_db
    ):
        owner = _make_doctor(db, test_tenant, username=f'{_DOCTOR_USER}_owner_{_tag()}')
        _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, owner, d, status='OPEN')
        t = _tick(db, v, d, status='waiting')
        resp = client.post(f'/doctor/call-patient/{v.id}')
        _assert_redirect_to(resp, '/doctor/patient-queue')
        db.session.expire_all()
        assert db.session.get(QueueManagement, t.id).status == 'waiting'

    def test_call_patient_wrong_role_403(self, app, client, db, test_tenant, rollback_db):
        nurse = _make_doctor(db, test_tenant, role='nurse', username=f'{_NURSE_USER}_{_tag()}')
        _login_as(client, db, test_tenant, nurse)
        doc = _make_doctor(db, test_tenant, username=f'{_DOCTOR_USER}_b_{_tag()}')
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='OPEN')
        resp = client.post(f'/doctor/call-patient/{v.id}')
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Notes surface
# ---------------------------------------------------------------------------


class TestNotes:
    def test_notes_page_renders(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        resp = client.get(f'/doctor/notes/{v.id}')
        assert resp.status_code == 200

    def test_notes_page_with_note_type(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        for note_type in ('lab', 'radiology', 'general', 'bogus-type'):
            resp = client.get(f'/doctor/notes/{v.id}?type={note_type}')
            assert resp.status_code == 200

    def test_post_empty_note_rerenders_form(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        resp = client.post(f'/doctor/notes/{v.id}', data={'medical_notes': '   '})
        assert resp.status_code == 200
        db.session.expire_all()
        assert not db.session.get(Visit, v.id).notes

    def test_post_oversized_note_rerenders_form(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        resp = client.post(f'/doctor/notes/{v.id}', data={'medical_notes': 'x' * 5001})
        assert resp.status_code == 200
        db.session.expire_all()
        assert 'x' * 5001 not in (db.session.get(Visit, v.id).notes or '')

    def test_post_note_appended_and_audited(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        resp = client.post(
            f'/doctor/notes/{v.id}',
            data={'medical_notes': 'المريض بخير', 'note_type': 'lab'},
        )
        _assert_redirect_to(resp, '/doctor/patient-queue')
        db.session.expire_all()
        v2 = db.session.get(Visit, v.id)
        assert 'المريض بخير' in v2.notes
        assert '[مذكرة تحاليل]' in v2.notes
        audits = (
            db.session.execute(select(AuditTrail).filter_by(entity_type='visit', entity_id=v.id))
            .scalars()
            .all()
        )
        assert any(a.description == 'إضافة ملاحظات طبية' for a in audits)

    def test_post_note_labels_for_each_type(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        for note_type, label in (
            ('lab', '[مذكرة تحاليل]'),
            ('radiology', '[مذكرة تصوير]'),
            ('general', '[مذكرة عامة]'),
            ('', '[ملاحظات طبية]'),
        ):
            v = _visit(db, p, doc, d, status='IN_PROGRESS')
            resp = client.post(
                f'/doctor/notes/{v.id}',
                data={'medical_notes': f'نص {note_type or "general"}', 'note_type': note_type},
            )
            _assert_redirect_to(resp, '/doctor/patient-queue')
            db.session.expire_all()
            assert label in (db.session.get(Visit, v.id).notes or '')

    def test_post_note_blocked_when_archived(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, archive_status='ARCHIVED')
        resp = client.post(f'/doctor/notes/{v.id}', data={'medical_notes': 'ممنوع'})
        _assert_redirect_to(resp, '/doctor/patient-queue')
        db.session.expire_all()
        assert not db.session.get(Visit, v.id).notes

    def test_notes_wrong_role_403(self, app, client, db, test_tenant, rollback_db):
        nurse = _make_doctor(db, test_tenant, role='nurse', username=f'{_NURSE_USER}_{_tag()}')
        _login_as(client, db, test_tenant, nurse)
        doc = _make_doctor(db, test_tenant, username=f'{_DOCTOR_USER}_c_{_tag()}')
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        resp = client.post(f'/doctor/notes/{v.id}', data={'medical_notes': 'x'})
        assert resp.status_code == 403

    def test_notes_missing_visit_redirects(self, app, client, db, test_tenant, rollback_db):
        _doctor_client(client, db, test_tenant)
        resp = client.get('/doctor/notes/99999999')
        _assert_redirect_to(resp, '/doctor/patient-queue')


class TestNoteTemplatesApi:
    def test_templates_crud_cycle(self, app, client, db, test_tenant, rollback_db):
        _doctor_client(client, db, test_tenant)

        resp = client.get('/doctor/api/note-templates')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        seeded = body['templates']
        assert len(seeded) >= 1  # defaults are seeded on first read
        for t in seeded:
            assert {'id', 'name', 'text', 'is_active'} <= set(t)

        resp = client.post(
            '/doctor/api/note-templates',
            json={'name': 'قالب التغطية', 'text': 'نص القالب'},
        )
        assert resp.status_code == 201
        new_id = resp.get_json()['id']
        assert new_id

        resp = client.get('/doctor/api/note-templates')
        names = [t['name'] for t in resp.get_json()['templates']]
        assert 'قالب التغطية' in names

        resp = client.post(
            '/doctor/api/note-templates',
            json={'id': new_id, 'name': 'اسم محدّث', 'text': 'نص محدّث', 'is_active': False},
        )
        assert resp.status_code == 200
        assert resp.get_json()['id'] == new_id
        resp = client.get('/doctor/api/note-templates?active_only=true')
        assert all(t['id'] != new_id for t in resp.get_json()['templates'])
        resp = client.get('/doctor/api/note-templates?active_only=false')
        updated = next(t for t in resp.get_json()['templates'] if t['id'] == new_id)
        assert updated['name'] == 'اسم محدّث'

        resp = client.post(f'/doctor/api/note-templates/{new_id}/delete')
        assert resp.status_code == 200
        assert resp.get_json()['success'] is True
        resp = client.post(f'/doctor/api/note-templates/{new_id}/delete')
        assert resp.status_code == 404

    def test_templates_validation_errors(self, app, client, db, test_tenant, rollback_db):
        _doctor_client(client, db, test_tenant)
        assert (
            client.post(
                '/doctor/api/note-templates', json={'name': 'x' * 101, 'text': 't'}
            ).status_code
            == 400
        )
        assert (
            client.post(
                '/doctor/api/note-templates', json={'name': 'ok', 'text': 't' * 5001}
            ).status_code
            == 400
        )
        assert (
            client.post('/doctor/api/note-templates', json={'name': '', 'text': 't'}).status_code
            == 400
        )
        resp = client.post(
            '/doctor/api/note-templates', json={'id': 'no-such-id', 'name': 'n', 'text': 't'}
        )
        assert resp.status_code == 404

    def test_note_templates_wrong_role_403(self, app, client, db, test_tenant, rollback_db):
        nurse = _make_doctor(db, test_tenant, role='nurse', username=f'{_NURSE_USER}_{_tag()}')
        _login_as(client, db, test_tenant, nurse)
        resp = client.get('/doctor/api/note-templates')
        assert resp.status_code == 403


class TestDashboardLayoutApi:
    def test_layout_get_returns_defaults(self, app, client, db, test_tenant, rollback_db):
        _doctor_client(client, db, test_tenant)
        resp = client.get('/doctor/api/dashboard-layout')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        ids = [i['id'] for i in body['items']]
        assert set(ids) == {'stats_overview', 'patients_actions', 'smart_insights'}

    def test_layout_post_normalizes_and_persists(self, app, client, db, test_tenant, rollback_db):
        _doctor_client(client, db, test_tenant)
        items = [
            {'id': 'smart_insights', 'order': '3', 'enabled': False, 'title': 'C'},
            {'id': 'stats_overview', 'order': '1', 'enabled': True, 'title': 'A'},
            {'id': 'bogus-panel', 'order': 9, 'enabled': True, 'title': 'X'},
            'garbage',
        ]
        resp = client.post('/doctor/api/dashboard-layout', json={'items': items})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        returned = body['items']
        assert [i['id'] for i in returned] == ['smart_insights', 'stats_overview']
        by_id = {i['id']: i for i in returned}
        assert by_id['smart_insights']['enabled'] is False
        assert by_id['smart_insights']['order'] == 3

        resp = client.get('/doctor/api/dashboard-layout')
        persisted = resp.get_json()['items']
        assert [i['id'] for i in persisted] == ['smart_insights', 'stats_overview']

    def test_layout_post_all_junk_falls_back_to_defaults(
        self, app, client, db, test_tenant, rollback_db
    ):
        _doctor_client(client, db, test_tenant)
        resp = client.post('/doctor/api/dashboard-layout', json={'items': [{'id': 'nope'}]})
        assert resp.status_code == 200
        assert {i['id'] for i in resp.get_json()['items']} == {
            'stats_overview',
            'patients_actions',
            'smart_insights',
        }

    def test_layout_post_bad_order_coerced_to_zero(self, app, client, db, test_tenant, rollback_db):
        _doctor_client(client, db, test_tenant)
        resp = client.post(
            '/doctor/api/dashboard-layout',
            json={'items': [{'id': 'stats_overview', 'order': 'not-a-number'}]},
        )
        assert resp.status_code == 200
        assert resp.get_json()['items'][0]['order'] == 0

    def test_dashboard_layout_wrong_role_403(self, app, client, db, test_tenant, rollback_db):
        nurse = _make_doctor(db, test_tenant, role='nurse', username=f'{_NURSE_USER}_{_tag()}')
        _login_as(client, db, test_tenant, nurse)
        resp = client.get('/doctor/api/dashboard-layout')
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Patients surface (search, history, timeline, dental chart)
# ---------------------------------------------------------------------------


class TestPatientsSearch:
    def test_patients_page_renders(self, app, client, db, test_tenant, rollback_db):
        _doctor_client(client, db, test_tenant)
        _patient(db)
        resp = client.get('/doctor/patients')
        assert resp.status_code == 200

    def test_patients_page_search_finds_by_exact_first_name(
        self, app, client, db, test_tenant, rollback_db
    ):
        _doctor_client(client, db, test_tenant)
        uname = f'Findable{_tag()}'
        _patient(db, first_name=uname)
        resp = client.get(f'/doctor/patients?q={uname}')
        assert resp.status_code == 200
        assert uname in resp.get_data(as_text=True)

    def test_patients_page_search_no_match(self, app, client, db, test_tenant, rollback_db):
        _doctor_client(client, db, test_tenant)
        resp = client.get(f'/doctor/patients?q=NoMatch{_tag()}')
        assert resp.status_code == 200

    def test_patients_wrong_role_403(self, app, client, db, test_tenant, rollback_db):
        nurse = _make_doctor(db, test_tenant, role='nurse', username=f'{_NURSE_USER}_{_tag()}')
        _login_as(client, db, test_tenant, nurse)
        resp = client.get('/doctor/patients')
        assert resp.status_code == 403

    def test_api_patient_search_returns_match(self, app, client, db, test_tenant, rollback_db):
        _doctor_client(client, db, test_tenant)
        uname = f'ApiFind{_tag()}'
        p = _patient(db, first_name=uname)
        resp = client.get(f'/doctor/api/patient-search?q={uname}')
        assert resp.status_code == 200
        body = resp.get_json()
        assert any(row['id'] == p.id for row in body['patients'])

    def test_api_patient_search_empty_query(self, app, client, db, test_tenant, rollback_db):
        _doctor_client(client, db, test_tenant)
        _patient(db)
        resp = client.get('/doctor/api/patient-search?q=')
        assert resp.status_code == 200
        assert 'patients' in resp.get_json()

    def test_api_patient_search_wrong_role_403(self, app, client, db, test_tenant, rollback_db):
        nurse = _make_doctor(db, test_tenant, role='nurse', username=f'{_NURSE_USER}_{_tag()}')
        _login_as(client, db, test_tenant, nurse)
        resp = client.get('/doctor/api/patient-search?q=x')
        assert resp.status_code == 403


class TestMedicalHistory:
    def test_medical_history_renders(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        _visit(db, p, doc, _department(db))
        resp = client.get(f'/doctor/medical-history/{p.id}')
        assert resp.status_code == 200

    def test_medical_history_missing_patient_redirects(
        self, app, client, db, test_tenant, rollback_db
    ):
        _doctor_client(client, db, test_tenant)
        resp = client.get('/doctor/medical-history/99999999')
        _assert_redirect_to(resp, '/doctor/patients')

    def test_prescriptions_history_renders(self, app, client, db, test_tenant, rollback_db):
        _doctor_client(client, db, test_tenant)
        p = _patient(db)
        resp = client.get(f'/doctor/prescriptions-history/{p.id}')
        assert resp.status_code == 200

    def test_prescriptions_history_missing_patient_redirects(
        self, app, client, db, test_tenant, rollback_db
    ):
        _doctor_client(client, db, test_tenant)
        resp = client.get('/doctor/prescriptions-history/99999999')
        _assert_redirect_to(resp, '/doctor/patients')

    def test_patient_timeline_renders(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        _visit(db, p, doc, _department(db))
        resp = client.get(f'/doctor/patient-timeline/{p.id}')
        assert resp.status_code == 200

    def test_patient_timeline_missing_patient_redirects(
        self, app, client, db, test_tenant, rollback_db
    ):
        _doctor_client(client, db, test_tenant)
        resp = client.get('/doctor/patient-timeline/99999999')
        _assert_redirect_to(resp, '/doctor/patients')

    def test_medical_records_redirects_to_patients(self, app, client, db, test_tenant, rollback_db):
        _doctor_client(client, db, test_tenant)
        resp = client.get('/doctor/medical-records')
        _assert_redirect_to(resp, '/doctor/patients')


class TestDentalChart:
    def test_dental_chart_renders(self, app, client, db, test_tenant, rollback_db):
        _doctor_client(client, db, test_tenant)
        p = _patient(db)
        resp = client.get(f'/doctor/dental-chart/{p.id}')
        assert resp.status_code == 200
        assert 'dentalSvg' in resp.get_data(as_text=True)

    def test_dental_chart_missing_patient_redirects(
        self, app, client, db, test_tenant, rollback_db
    ):
        _doctor_client(client, db, test_tenant)
        resp = client.get('/doctor/dental-chart/99999999')
        _assert_redirect_to(resp, '/doctor/patients')

    def test_save_dental_chart_persists_teeth(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        payload = {
            'patient_id': p.id,
            'visit_id': None,
            'teeth': {
                '11': {'state': 'caries', 'surfaces': {'occlusal': 'caries'}, 'notes': 'حشوة'},
                '12': {'state': 'sound'},  # sound + no notes/surfaces -> skipped
                '46': {'state': 'filling', 'surfaces': {}, 'notes': ''},
                '99': 'not-a-dict',  # non-dict entries are skipped
            },
            'notes': 'مراجعة دورية',
        }
        resp = client.post('/doctor/dental-chart/save', json=payload)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['success'] is True
        chart_id = body['chart_id']

        chart = db.session.get(DentalChart, chart_id)
        assert chart is not None
        assert chart.patient_id == p.id
        assert chart.doctor_id == doc.id
        assert chart.notes == 'مراجعة دورية'

        teeth = db.session.execute(select(DentalTooth).filter_by(chart_id=chart_id)).scalars().all()
        by_fdi = {t.fdi_number: t for t in teeth}
        assert set(by_fdi) == {'11', '46'}
        assert by_fdi['11'].state == 'caries'
        assert by_fdi['11'].surfaces == {'occlusal': 'caries'}
        assert by_fdi['11'].notes == 'حشوة'
        assert by_fdi['46'].state == 'filling'

    def test_save_dental_chart_rejects_bad_patient_id(
        self, app, client, db, test_tenant, rollback_db
    ):
        _doctor_client(client, db, test_tenant)
        resp = client.post('/doctor/dental-chart/save', json={'patient_id': 'abc'})
        assert resp.status_code == 422
        assert resp.get_json()['success'] is False

    def test_save_dental_chart_rejects_bad_visit_id(
        self, app, client, db, test_tenant, rollback_db
    ):
        _doctor_client(client, db, test_tenant)
        p = _patient(db)
        resp = client.post(
            '/doctor/dental-chart/save',
            json={'patient_id': p.id, 'visit_id': 'not-a-number', 'teeth': {}},
        )
        assert resp.status_code == 422
        assert resp.get_json()['success'] is False

    def test_save_dental_chart_rejects_non_dict_teeth(
        self, app, client, db, test_tenant, rollback_db
    ):
        _doctor_client(client, db, test_tenant)
        p = _patient(db)
        resp = client.post(
            '/doctor/dental-chart/save',
            json={'patient_id': p.id, 'teeth': 'not-a-dict'},
        )
        assert resp.status_code == 422
        assert resp.get_json()['success'] is False

    def test_save_dental_chart_wrong_role_403(self, app, client, db, test_tenant, rollback_db):
        nurse = _make_doctor(db, test_tenant, role='nurse', username=f'{_NURSE_USER}_{_tag()}')
        _login_as(client, db, test_tenant, nurse)
        p = _patient(db)
        resp = client.post('/doctor/dental-chart/save', json={'patient_id': p.id, 'teeth': {}})
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Lab surface
# ---------------------------------------------------------------------------


class TestLabRequests:
    def test_get_lab_request_redirects_to_patient_details(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        resp = client.get(f'/doctor/lab-request/{v.id}')
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')

    def test_lab_request_requires_in_progress(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='OPEN')
        resp = client.post(f'/doctor/lab-request/{v.id}', data={'test_name': 'CBC'})
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        db.session.expire_all()
        assert not db.session.get(Visit, v.id).lab_tests_ordered

    def test_lab_request_memo_creates_note_and_flag(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        reception = _department(db, name='Reception', reception=True)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        resp = client.post(
            f'/doctor/lab-request/{v.id}',
            data={'test_name': 'تحليل دم', 'notes': 'صائم منذ 12 ساعة', 'urgency': 'عادية'},
        )
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        db.session.expire_all()
        v2 = db.session.get(Visit, v.id)
        assert v2.lab_tests_ordered is True
        assert '[مذكرة تحاليل]' in v2.notes
        assert 'تحليل دم' in v2.notes
        assert v2.department_id == reception.id
        assert v2.pending_financial_settlement is True
        audits = (
            db.session.execute(select(AuditTrail).filter_by(entity_type='lab_test', entity_id=v.id))
            .scalars()
            .all()
        )
        assert any('مذكرة تحاليل' in (a.description or '') for a in audits)

    def test_lab_request_oversized_test_name_rejected(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        resp = client.post(f'/doctor/lab-request/{v.id}', data={'test_name': 'x' * 201})
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        db.session.expire_all()
        assert not db.session.get(Visit, v.id).lab_tests_ordered

    def test_lab_request_structured_creates_catalog_backed_order(
        self, app, client, db, test_tenant, rollback_db
    ):
        from models.lab_test_catalog import LabTestCatalog

        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        cat = LabTestCatalog(
            code=f'COV{_tag()[:6].upper()}',
            name_ar='صورة دم كاملة',
            name_en='CBC',
            category='hematology',
            price=50,
        )
        db.session.add(cat)
        db.session.commit()

        resp = client.post(
            f'/doctor/lab-request/{v.id}',
            data={'test_ids': str(cat.id), 'notes': 'متابعة'},
        )
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        requests = db.session.execute(select(LabRequest).filter_by(visit_id=v.id)).scalars().all()
        assert len(requests) == 1
        assert requests[0].patient_id == p.id
        results = (
            db.session.execute(select(LabResult).filter_by(request_id=requests[0].id))
            .scalars()
            .all()
        )
        assert any(r.test_code == cat.code for r in results)

    def test_lab_request_wrong_role_403(self, app, client, db, test_tenant, rollback_db):
        nurse = _make_doctor(db, test_tenant, role='nurse', username=f'{_NURSE_USER}_{_tag()}')
        _login_as(client, db, test_tenant, nurse)
        doc = _make_doctor(db, test_tenant, username=f'{_DOCTOR_USER}_d_{_tag()}')
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        resp = client.post(f'/doctor/lab-request/{v.id}', data={'test_name': 'CBC'})
        assert resp.status_code == 403

    def test_lab_results_page_renders(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db, first_name='Labcase', last_name='Result')
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
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
                test_name='صورة دم كاملة',
                value='12.5',
                status=LabResultStatus.VALIDATED.value,
                is_critical=True,
            )
        )
        db.session.commit()
        resp = client.get(f'/doctor/lab-results/{p.id}')
        assert resp.status_code == 200
        assert 'Labcase' in resp.get_data(as_text=True)

    def test_lab_results_missing_patient_redirects(self, app, client, db, test_tenant, rollback_db):
        _doctor_client(client, db, test_tenant)
        resp = client.get('/doctor/lab-results/99999999')
        _assert_redirect_to(resp, '/doctor/patient-queue')

    def test_lab_requests_index_redirects(self, app, client, db, test_tenant, rollback_db):
        _doctor_client(client, db, test_tenant)
        resp = client.get('/doctor/lab-requests')
        _assert_redirect_to(resp, '/doctor/patient-queue')


# ---------------------------------------------------------------------------
# Radiology surface
# ---------------------------------------------------------------------------


class TestRadiologyRequests:
    def test_get_radiology_request_redirects(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        resp = client.get(f'/doctor/radiology-request/{v.id}')
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')

    def test_radiology_request_requires_in_progress(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='OPEN')
        resp = client.post(f'/doctor/radiology-request/{v.id}', data={'test_name': 'X-Ray'})
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        db.session.expire_all()
        assert not db.session.get(Visit, v.id).radiology_ordered

    def test_radiology_request_structured_creates_order(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        reception = _department(db, name='Reception', reception=True)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        resp = client.post(
            f'/doctor/radiology-request/{v.id}',
            data={
                'test_name': 'أشعة صدر',
                'modality': 'XR',
                'body_part': 'chest',
                'notes': 'ضيق تنفس',
            },
        )
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        db.session.expire_all()
        v2 = db.session.get(Visit, v.id)
        assert v2.radiology_ordered is True
        assert '[مذكرة تصوير]' in v2.notes
        assert v2.department_id == reception.id
        assert v2.pending_financial_settlement is True
        requests = (
            db.session.execute(select(RadiologyRequest).filter_by(visit_id=v.id)).scalars().all()
        )
        assert len(requests) == 1
        assert requests[0].modality == 'XR'
        assert requests[0].body_part == 'chest'

    def test_radiology_request_oversized_modality_rejected(
        self, app, client, db, test_tenant, rollback_db
    ):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        resp = client.post(f'/doctor/radiology-request/{v.id}', data={'modality': 'x' * 51})
        _assert_redirect_to(resp, f'/doctor/patient-details/{v.id}')
        db.session.expire_all()
        assert not db.session.get(Visit, v.id).radiology_ordered

    def test_radiology_request_wrong_role_403(self, app, client, db, test_tenant, rollback_db):
        nurse = _make_doctor(db, test_tenant, role='nurse', username=f'{_NURSE_USER}_{_tag()}')
        _login_as(client, db, test_tenant, nurse)
        doc = _make_doctor(db, test_tenant, username=f'{_DOCTOR_USER}_e_{_tag()}')
        p = _patient(db)
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
        resp = client.post(f'/doctor/radiology-request/{v.id}', data={'test_name': 'MRI'})
        assert resp.status_code == 403

    def test_radiology_results_page_renders(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db, first_name='Radcase', last_name='Result')
        d = _department(db)
        v = _visit(db, p, doc, d, status='IN_PROGRESS')
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
        resp = client.get(f'/doctor/radiology-results/{p.id}')
        assert resp.status_code == 200

    def test_radiology_results_missing_patient_redirects(
        self, app, client, db, test_tenant, rollback_db
    ):
        _doctor_client(client, db, test_tenant)
        resp = client.get('/doctor/radiology-results/99999999')
        _assert_redirect_to(resp, '/doctor/patient-queue')

    def test_radiology_requests_index_redirects(self, app, client, db, test_tenant, rollback_db):
        _doctor_client(client, db, test_tenant)
        resp = client.get('/doctor/radiology-requests')
        _assert_redirect_to(resp, '/doctor/patient-queue')


# ---------------------------------------------------------------------------
# Appointments surface (and role matrix)
# ---------------------------------------------------------------------------


class TestAppointments:
    def test_appointments_page_renders_after_fix(self, app, client, db, test_tenant, rollback_db):
        doc = _doctor_client(client, db, test_tenant)
        p = _patient(db, first_name='Apptcheck', last_name='Person')
        d = _department(db)
        db.session.add(
            Appointment(
                patient_id=p.id,
                doctor_id=doc.id,
                department_id=d.id,
                starts_at=datetime.now(UTC) + timedelta(hours=1),
                status='CONFIRMED',
            )
        )
        db.session.commit()
        resp = client.get('/doctor/appointments')
        assert resp.status_code == 200
        assert 'Apptcheck' in resp.get_data(as_text=True)

    def test_appointments_wrong_role_403(self, app, client, db, test_tenant, rollback_db):
        nurse = _make_doctor(db, test_tenant, role='nurse', username=f'{_NURSE_USER}_{_tag()}')
        _login_as(client, db, test_tenant, nurse)
        resp = client.get('/doctor/appointments')
        assert resp.status_code == 403


class TestRoleMatrix:
    def test_anonymous_redirected_to_login(self, app, client, db, test_tenant, rollback_db):
        for path in ('/doctor/patient-queue', '/doctor/dashboard', '/doctor/appointments'):
            resp = client.get(path)
            assert resp.status_code == 302
            assert '/auth/login' in resp.headers.get('Location', '')

    def test_non_clinical_roles_get_403(self, app, client, db, test_tenant, rollback_db):
        for role in ('nurse', 'pharmacist', 'reception', 'accountant'):
            user = _make_doctor(db, test_tenant, role=role, username=f'doccov_{role}_{_tag()}')
            _login_as(client, db, test_tenant, user)
            resp = client.get('/doctor/patient-queue')
            assert resp.status_code == 403, role
