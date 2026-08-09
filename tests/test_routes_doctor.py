"""HTTP route tests for the doctor blueprint."""

import json
import types
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.extensions import db
from app.shared.enums import VisitState
from models.appointment import Appointment
from models.department import Department
from models.patient import Patient
from models.user import User
from models.visit import Visit


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


@pytest.fixture
def ctx(app, db, test_tenant):
    tenant_id = test_tenant.id

    def _patient(**kw):
        p = Patient(
            first_name=kw.get('first_name', 'مريض'),
            last_name=kw.get('last_name', 'طبيب'),
            phone=kw.get('phone', '050' + format(uuid.uuid4().int % 10**7, '07d')),
            gender=kw.get('gender', 'M'),
        )
        db.session.add(p)
        db.session.commit()
        return p

    def _department(**kw):
        tag = uuid.uuid4().hex[:6]
        d = Department(
            name=kw.get('name', f'Dept-{tag}'),
            name_ar=kw.get('name_ar', f'قسم-{tag}'),
            is_active=True,
        )
        db.session.add(d)
        db.session.commit()
        return d

    def _user(**kw):
        role = kw.get('role', 'doctor')
        u = User(
            username=kw.get('username', f'{role}_{uuid.uuid4().hex[:6]}'),
            email=kw.get('email', f'{uuid.uuid4().hex[:8]}@test.local'),
            full_name=kw.get('full_name', 'طبيب اختبار'),
            role=role,
            is_active=True,
        )
        u.set_password('test123')
        db.session.add(u)
        db.session.commit()
        return u

    def _visit(**kw):
        v = Visit(
            patient_id=kw.get('patient_id'),
            department_id=kw.get('department_id'),
            doctor_id=kw.get('doctor_id'),
            status=kw.get('status', VisitState.OPEN.value),
            payment_status=kw.get('payment_status', 'PENDING'),
            total_amount=kw.get('total_amount', 0),
            visit_type=kw.get('visit_type', 'REGULAR'),
            payment_method=kw.get('payment_method', 'cash'),
        )
        db.session.add(v)
        db.session.commit()
        return v

    def _appointment(**kw):
        starts = datetime.now(UTC) + timedelta(hours=2)
        apt = Appointment(
            patient_id=kw.get('patient_id'),
            department_id=kw.get('department_id'),
            doctor_id=kw.get('doctor_id'),
            starts_at=kw.get('starts_at', starts),
            status=kw.get('status', 'SCHEDULED'),
        )
        db.session.add(apt)
        db.session.commit()
        return apt

    return types.SimpleNamespace(
        db=db,
        tenant_id=tenant_id,
        patient=_patient,
        department=_department,
        user=_user,
        visit=_visit,
        appointment=_appointment,
    )


def _make_doctor(login_as, client, ctx):
    doc = ctx.user(role='doctor')
    login_as(client, doc.username, 'doctor')
    return doc


class TestDoctorDashboard:
    def test_dashboard_renders(self, login_as, client, ctx):
        _make_doctor(login_as, client, ctx)
        resp = client.get('/doctor/dashboard')
        assert resp.status_code == 200

    def test_dashboard_new(self, login_as, client, ctx):
        _make_doctor(login_as, client, ctx)
        resp = client.get('/doctor/dashboard-new')
        assert resp.status_code in (200, 302)

    def test_api_dashboard_stats(self, login_as, client, ctx):
        _make_doctor(login_as, client, ctx)
        resp = client.get(
            '/doctor/api/dashboard-stats',
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code in (200, 302)

    def test_api_today_visits(self, login_as, client, ctx):
        _make_doctor(login_as, client, ctx)
        resp = client.get(
            '/doctor/api/today-visits',
            headers={'Accept': 'application/json'},
        )
        assert resp.status_code in (200, 302)


class TestDoctorVisits:
    def test_visits_list(self, login_as, client, ctx):
        doc = _make_doctor(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        ctx.visit(patient_id=p.id, department_id=d.id, doctor_id=doc.id)
        resp = client.get('/doctor/visits')
        assert resp.status_code in (200, 302)

    def test_patient_details(self, login_as, client, ctx):
        doc = _make_doctor(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        v = ctx.visit(patient_id=p.id, department_id=d.id, doctor_id=doc.id)
        resp = client.get(f'/doctor/patient-details/{v.id}')
        assert resp.status_code == 200

    def test_view_patient(self, login_as, client, ctx):
        doc = _make_doctor(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        v = ctx.visit(patient_id=p.id, department_id=d.id, doctor_id=doc.id)
        resp = client.get(f'/doctor/view_patient/{v.id}')
        assert resp.status_code in (200, 302)

    def test_visit_summary(self, login_as, client, ctx):
        doc = _make_doctor(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        v = ctx.visit(patient_id=p.id, department_id=d.id, doctor_id=doc.id, status='COMPLETED')
        resp = client.get(f'/doctor/visit-summary/{v.id}')
        assert resp.status_code in (200, 302)

    def test_save_visit_summary(self, login_as, client, ctx):
        doc = _make_doctor(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        v = ctx.visit(patient_id=p.id, department_id=d.id, doctor_id=doc.id, status='COMPLETED')
        resp = client.post(
            f'/doctor/save-visit-summary/{v.id}',
            data={
                'diagnosis': 'فحص عام',
                'treatment_plan': 'راحة',
                'follow_up_required': 'false',
            },
        )
        assert resp.status_code in (302, 200)

    def test_start_treatment(self, login_as, client, ctx):
        doc = _make_doctor(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        v = ctx.visit(patient_id=p.id, department_id=d.id, doctor_id=doc.id)
        resp = client.post(f'/doctor/start-treatment/{v.id}')
        assert resp.status_code in (302, 200)

    def test_end_treatment(self, login_as, client, ctx):
        doc = _make_doctor(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        v = ctx.visit(patient_id=p.id, department_id=d.id, doctor_id=doc.id, status='TREATING')
        resp = client.post(f'/doctor/end-treatment/{v.id}')
        assert resp.status_code in (302, 200)
        ctx.db.session.refresh(v)


class TestDoctorDiagnosis:
    def test_diagnosis_get(self, login_as, client, ctx):
        doc = _make_doctor(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        v = ctx.visit(patient_id=p.id, department_id=d.id, doctor_id=doc.id)
        resp = client.get(f'/doctor/diagnosis/{v.id}')
        assert resp.status_code == 200

    def test_diagnosis_post(self, login_as, client, ctx):
        doc = _make_doctor(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        v = ctx.visit(patient_id=p.id, department_id=d.id, doctor_id=doc.id)
        resp = client.post(
            f'/doctor/diagnosis/{v.id}',
            data={
                'chief_complaint': 'صداع',
                'diagnosis': 'صداع نصفي',
                'treatment_plan': 'مسكنات',
                'differential_diagnosis': '',
                'follow_up_required': 'false',
            },
        )
        assert resp.status_code in (302, 200)


class TestDoctorPrescriptions:
    def test_prescriptions_list(self, login_as, client, ctx):
        _make_doctor(login_as, client, ctx)
        resp = client.get('/doctor/prescriptions')
        assert resp.status_code in (200, 302)

    def test_prescription_get(self, login_as, client, ctx):
        doc = _make_doctor(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        v = ctx.visit(patient_id=p.id, department_id=d.id, doctor_id=doc.id, status='COMPLETED')
        resp = client.get(f'/doctor/prescription/{v.id}')
        assert resp.status_code in (200, 302)


class TestDoctorNotes:
    def test_notes_get(self, login_as, client, ctx):
        doc = _make_doctor(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        v = ctx.visit(patient_id=p.id, department_id=d.id, doctor_id=doc.id, status='COMPLETED')
        resp = client.get(f'/doctor/notes/{v.id}')
        assert resp.status_code == 200

    def test_notes_post(self, login_as, client, ctx):
        doc = _make_doctor(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        v = ctx.visit(patient_id=p.id, department_id=d.id, doctor_id=doc.id, status='COMPLETED')
        resp = client.post(
            f'/doctor/notes/{v.id}',
            data={
                'subjective': 'ألم بطني',
                'objective': 'فحص طبيعي',
                'assessment': 'التهاب خفيف',
                'plan': 'مضادات',
                'note_type': 'progress',
            },
        )
        assert resp.status_code in (302, 200)

    def test_note_templates_get(self, login_as, client, ctx):
        _make_doctor(login_as, client, ctx)
        resp = client.get('/doctor/api/note-templates')
        assert resp.status_code in (200, 302)

    def test_dashboard_layout_get(self, login_as, client, ctx):
        _make_doctor(login_as, client, ctx)
        resp = client.get('/doctor/api/dashboard-layout')
        assert resp.status_code in (200, 302)


class TestDoctorPatients:
    def test_patients_list(self, login_as, client, ctx):
        doc = _make_doctor(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        ctx.visit(patient_id=p.id, department_id=d.id, doctor_id=doc.id)
        resp = client.get('/doctor/patients')
        assert resp.status_code == 200

    def test_medical_history(self, login_as, client, ctx):
        doc = _make_doctor(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        ctx.visit(patient_id=p.id, department_id=d.id, doctor_id=doc.id)
        resp = client.get(f'/doctor/medical-history/{p.id}')
        assert resp.status_code == 200

    def test_patient_timeline(self, login_as, client, ctx):
        doc = _make_doctor(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        ctx.visit(patient_id=p.id, department_id=d.id, doctor_id=doc.id)
        resp = client.get(f'/doctor/patient-timeline/{p.id}')
        assert resp.status_code == 200

    def test_print_medical_report(self, login_as, client, ctx):
        doc = _make_doctor(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        v = ctx.visit(patient_id=p.id, department_id=d.id, doctor_id=doc.id, status='COMPLETED')
        resp = client.get(f'/doctor/print-medical-report/{v.id}')
        assert resp.status_code in (200, 302)

    def test_api_patient_search(self, login_as, client, ctx):
        doc = _make_doctor(login_as, client, ctx)
        p = ctx.patient(first_name='بحثطبيب')
        resp = client.get(
            '/doctor/api/patient-search',
            query_string={'q': 'بحثطبيب'},
        )
        assert resp.status_code in (200, 302)


class TestDoctorQueue:
    def test_patient_queue(self, login_as, client, ctx):
        doc = _make_doctor(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        ctx.visit(patient_id=p.id, department_id=d.id, doctor_id=doc.id)
        resp = client.get('/doctor/patient-queue')
        assert resp.status_code == 200

    def test_call_patient(self, login_as, client, ctx):
        doc = _make_doctor(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        v = ctx.visit(patient_id=p.id, department_id=d.id, doctor_id=doc.id)
        resp = client.post(f'/doctor/call-patient/{v.id}')
        assert resp.status_code in (302, 200)


class TestDoctorLab:
    def test_lab_requests(self, login_as, client, ctx):
        _make_doctor(login_as, client, ctx)
        resp = client.get('/doctor/lab-requests')
        assert resp.status_code in (200, 302)

    def test_lab_request_get(self, login_as, client, ctx):
        doc = _make_doctor(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        v = ctx.visit(patient_id=p.id, department_id=d.id, doctor_id=doc.id, status='TREATING')
        resp = client.get(f'/doctor/lab-request/{v.id}')
        assert resp.status_code == 200


class TestDoctorRadiology:
    def test_radiology_requests(self, login_as, client, ctx):
        _make_doctor(login_as, client, ctx)
        resp = client.get('/doctor/radiology-requests')
        assert resp.status_code in (200, 302)

    def test_radiology_request_get(self, login_as, client, ctx):
        doc = _make_doctor(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        v = ctx.visit(patient_id=p.id, department_id=d.id, doctor_id=doc.id, status='TREATING')
        resp = client.get(f'/doctor/radiology-request/{v.id}')
        assert resp.status_code == 200


class TestDoctorAppointments:
    def test_appointments_list(self, login_as, client, ctx):
        doc = _make_doctor(login_as, client, ctx)
        p = ctx.patient()
        d = ctx.department()
        ctx.appointment(patient_id=p.id, department_id=d.id, doctor_id=doc.id)
        resp = client.get('/doctor/appointments')
        assert resp.status_code in (200, 302)
