"""HTTP route tests for lab, radiology, medication, and accountant blueprints."""

import json
import types
import uuid
from datetime import UTC, datetime

import pytest

from app.extensions import db
from app.shared.enums import VisitState
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

    return types.SimpleNamespace(
        db=db,
        tenant_id=tenant_id,
        patient=_patient,
        department=_department,
        user=_user,
        visit=_visit,
    )


def _make_role(login_as, client, ctx, role):
    u = ctx.user(role=role)
    login_as(client, u.username, role)
    return u


class TestLabRoutes:
    def test_dashboard(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'lab')
        resp = client.get('/lab/dashboard')
        assert resp.status_code in (200, 302, 403)

    def test_index(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'lab')
        resp = client.get('/lab/')
        assert resp.status_code in (200, 302, 403)

    def test_requests(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'lab')
        resp = client.get('/lab/requests')
        assert resp.status_code in (200, 302, 403)

    def test_results(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'lab')
        resp = client.get('/lab/results')
        assert resp.status_code in (200, 302, 403)

    def test_tests(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'lab')
        resp = client.get('/lab/tests')
        assert resp.status_code in (200, 302, 403)

    def test_worklist(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'lab')
        resp = client.get('/lab/worklist')
        assert resp.status_code in (200, 302, 403)

    def test_quality(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'lab')
        resp = client.get('/lab/quality')
        assert resp.status_code in (200, 302, 403)

    def test_reagents(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'lab')
        resp = client.get('/lab/reagents')
        assert resp.status_code in (200, 302, 403)

    def test_reports(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'lab')
        resp = client.get('/lab/reports')
        assert resp.status_code in (200, 302, 403)

    def test_test_catalog(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'lab')
        resp = client.get('/lab/test-catalog/')
        assert resp.status_code in (200, 302, 403)

    def test_api_worklist(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'lab')
        resp = client.get('/lab/api/worklist')
        assert resp.status_code in (200, 302, 403)


class TestRadiologyRoutes:
    def test_dashboard(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'radiology')
        resp = client.get('/radiology/dashboard')
        assert resp.status_code in (200, 302, 403)

    def test_index(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'radiology')
        resp = client.get('/radiology/')
        assert resp.status_code in (200, 302, 403)

    def test_requests(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'radiology')
        resp = client.get('/radiology/requests')
        assert resp.status_code in (200, 302, 403)

    def test_results(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'radiology')
        resp = client.get('/radiology/results')
        assert resp.status_code in (200, 302, 403)

    def test_images(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'radiology')
        resp = client.get('/radiology/images')
        assert resp.status_code in (200, 302, 403)

    def test_quality(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'radiology')
        resp = client.get('/radiology/quality')
        assert resp.status_code in (200, 302, 403)

    def test_worklist(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'radiology')
        resp = client.get('/radiology/worklist')
        assert resp.status_code in (200, 302, 403)

    def test_reports(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'radiology')
        resp = client.get('/radiology/reports')
        assert resp.status_code in (200, 302, 403)


class TestMedicationRoutes:
    def test_dashboard(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'pharmacist')
        resp = client.get('/medication/dashboard')
        assert resp.status_code in (200, 302, 403)

    def test_index(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'pharmacist')
        resp = client.get('/medication/')
        assert resp.status_code in (200, 302, 403)

    def test_list(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'pharmacist')
        resp = client.get('/medication/list')
        assert resp.status_code in (200, 302, 403)

    def test_add_get(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'pharmacist')
        resp = client.get('/medication/add')
        assert resp.status_code in (200, 302, 403)

    def test_stock_alerts(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'pharmacist')
        resp = client.get('/medication/stock-alerts')
        assert resp.status_code in (200, 302, 403)

    def test_sales_history(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'pharmacist')
        resp = client.get('/medication/sales-history')
        assert resp.status_code in (200, 302, 403)

    def test_consumption_report(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'pharmacist')
        resp = client.get('/medication/consumption-report')
        assert resp.status_code in (200, 302, 403)

    def test_interactions(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'pharmacist')
        resp = client.get('/medication/interactions')
        assert resp.status_code in (200, 302, 403)

    def test_pos(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'pharmacist')
        resp = client.get('/medication/pos')
        assert resp.status_code in (200, 302, 403)


class TestAccountantRoutes:
    def test_dashboard(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'accountant')
        resp = client.get('/accountant/dashboard')
        assert resp.status_code in (200, 302, 403)

    def test_index(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'accountant')
        resp = client.get('/accountant/')
        assert resp.status_code in (200, 302, 403)

    def test_financial_report(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'accountant')
        resp = client.get('/accountant/financial-report')
        assert resp.status_code in (200, 302, 403)

    def test_daily_summary(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'accountant')
        resp = client.get('/accountant/daily-summary')
        assert resp.status_code in (200, 302, 403)

    def test_reports(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'accountant')
        resp = client.get('/accountant/reports')
        assert resp.status_code in (200, 302, 403)

    def test_invoices(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'accountant')
        resp = client.get('/accountant/invoices')
        assert resp.status_code in (200, 302, 403)

    def test_payments(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'accountant')
        resp = client.get('/accountant/payments')
        assert resp.status_code in (200, 302, 403)

    def test_audit_daily(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'accountant')
        resp = client.get('/accountant/audit/daily')
        assert resp.status_code in (200, 302, 403)
