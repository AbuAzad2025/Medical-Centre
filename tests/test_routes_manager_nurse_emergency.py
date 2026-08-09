"""HTTP route tests for manager, nurse, and emergency blueprints."""

import types
import uuid
from datetime import UTC, datetime, timedelta

import pytest

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
            last_name=kw.get('last_name', 'اختبار'),
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
            full_name=kw.get('full_name', 'مستخدم'),
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


def _make_role(login_as, client, ctx, role):
    u = ctx.user(role=role)
    login_as(client, u.username, role)
    return u


class TestManagerRoutes:
    def test_dashboard(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'manager')
        resp = client.get('/manager/dashboard')
        assert resp.status_code in (200, 302)

    def test_force_payment_approvals(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'manager')
        resp = client.get('/manager/force-payment-approvals')
        assert resp.status_code in (200, 302)

    def test_approve_force_payment(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'manager')
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        v = ctx.visit(patient_id=p.id, department_id=d.id, doctor_id=doc.id, is_force_payment=True, total_amount=100, paid_amount=0)
        resp = client.post(f'/manager/approve-force-payment/{v.id}')
        assert resp.status_code in (302, 200)

    def test_reject_force_payment(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'manager')
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        v = ctx.visit(patient_id=p.id, department_id=d.id, doctor_id=doc.id, is_force_payment=True, total_amount=100, paid_amount=0)
        resp = client.post(f'/manager/reject-force-payment/{v.id}')
        assert resp.status_code in (302, 200)

    def test_custom_service_approvals(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'manager')
        resp = client.get('/manager/custom-service-approvals')
        assert resp.status_code in (200, 302)

    def test_settlements(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'manager')
        resp = client.get('/manager/settlements')
        assert resp.status_code in (200, 302)

    def test_financial_reports(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'manager')
        resp = client.get('/manager/financial-reports')
        assert resp.status_code in (200, 302)

    def test_budget(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'manager')
        resp = client.get('/manager/budget')
        assert resp.status_code in (200, 302)

    def test_pricing(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'manager')
        resp = client.get('/manager/pricing')
        assert resp.status_code in (200, 302)

    def test_reports(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'manager')
        resp = client.get('/manager/reports')
        assert resp.status_code in (200, 302)

    def test_reports_center(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'manager')
        resp = client.get('/manager/reports-center')
        assert resp.status_code in (200, 302)

    def test_analytics(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'manager')
        resp = client.get('/manager/analytics')
        assert resp.status_code in (200, 302)

    def test_settings(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'manager')
        resp = client.get('/manager/settings')
        assert resp.status_code in (200, 302)

    def test_staff_schedule(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'manager')
        resp = client.get('/manager/staff/schedule')
        assert resp.status_code in (200, 302)

    def test_staff_absence(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'manager')
        resp = client.get('/manager/staff/absence')
        assert resp.status_code in (200, 302)

    def test_staff_list(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'manager')
        resp = client.get('/manager/staff')
        assert resp.status_code in (200, 302)

    def test_api_pricing_services_get(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'manager')
        resp = client.get('/manager/api/pricing/services')
        assert resp.status_code in (200, 302)


class TestNurseRoutes:
    def test_dashboard(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'nurse')
        resp = client.get('/nurse/dashboard')
        assert resp.status_code in (200, 302)

    def test_index(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'nurse')
        resp = client.get('/nurse/')
        assert resp.status_code in (200, 302)

    def test_patient_care(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'nurse')
        resp = client.get('/nurse/patient-care')
        assert resp.status_code in (200, 302)

    def test_medications(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'nurse')
        resp = client.get('/nurse/medications')
        assert resp.status_code in (200, 302)

    def test_vital_signs(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'nurse')
        resp = client.get('/nurse/vital-signs')
        assert resp.status_code in (200, 302)

    def test_tasks(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'nurse')
        resp = client.get('/nurse/tasks')
        assert resp.status_code in (200, 302)

    def test_patients(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'nurse')
        resp = client.get('/nurse/patients')
        assert resp.status_code in (200, 302)


class TestEmergencyRoutes:
    def test_dashboard(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'emergency')
        resp = client.get('/emergency/dashboard')
        assert resp.status_code in (200, 302)

    def test_index(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'emergency')
        resp = client.get('/emergency/')
        assert resp.status_code in (200, 302)

    def test_cases(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'emergency')
        resp = client.get('/emergency/cases')
        assert resp.status_code in (200, 302)

    def test_reports(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'emergency')
        resp = client.get('/emergency/reports')
        assert resp.status_code in (200, 302)

    def test_triage(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'emergency')
        resp = client.get('/emergency/triage')
        assert resp.status_code in (200, 302)

    def test_patient_queue(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'emergency')
        resp = client.get('/emergency/patient-queue')
        assert resp.status_code in (200, 302)

    def test_queue(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'emergency')
        resp = client.get('/emergency/queue')
        assert resp.status_code in (200, 302)

    def test_patients(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'emergency')
        resp = client.get('/emergency/patients')
        assert resp.status_code in (200, 302)
