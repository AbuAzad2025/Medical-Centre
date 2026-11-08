"""HTTP route tests for the super_admin performance metrics API."""

import types
import uuid

import pytest

from models.patient import Patient
from models.user import User


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
    db_ = db

    def _user(**kw):
        role = kw.get('role', 'doctor')
        u = User(
            username=kw.get('username', f'{role}_{uuid.uuid4().hex[:6]}'),
            email=kw.get('email', f'{uuid.uuid4().hex[:8]}@test.local'),
            full_name=kw.get('full_name', 'Test User'),
            role=role,
            is_active=True,
        )
        u.set_password('test123')
        db_.session.add(u)
        db_.session.commit()
        return u

    return types.SimpleNamespace(db=db_, tenant_id=tenant_id, user=_user)


class TestPerformanceMetricsAccessControl:
    def test_requires_super_admin(self, client):
        resp = client.get('/super-admin/api/performance')
        assert resp.status_code in (302, 401, 403)

    def test_regular_role_is_rejected(self, login_as, client, ctx):
        u = ctx.user(role='doctor')
        login_as(client, u.username, 'doctor')
        resp = client.get('/super-admin/api/performance')
        assert resp.status_code in (302, 401, 403)


class TestPerformanceMetrics:
    def test_returns_real_metrics_for_super_admin(self, login_as, client, ctx):
        u = ctx.user(role='super_admin')
        login_as(client, u.username, 'super_admin')
        resp = client.get('/super-admin/api/performance')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        # Real host metrics, never random
        assert 0 <= data['cpu_percent'] <= 100
        assert 0 <= data['memory_percent'] <= 100
        assert 0 <= data['disk_percent'] <= 100
        assert data['uptime_hours'] >= 0
        if data['active_db_connections'] is not None:
            assert data['active_db_connections'] >= 0
        if data['db_size_mb'] is not None:
            assert data['db_size_mb'] >= 0
        if data['visits_today'] is not None:
            assert data['visits_today'] >= 0
        if data['payments_today'] is not None:
            assert data['payments_today'] >= 0
        if data['prescriptions_today'] is not None:
            assert data['prescriptions_today'] >= 0

    def test_reports_real_db_counters_when_data_exists(self, db, app, login_as, client, ctx):
        from models.department import Department
        from models.visit import Visit

        u = ctx.user(role='super_admin')
        patient = Patient(
            first_name='Test',
            last_name='Performance',
            gender='M',
            phone='050' + format(uuid.uuid4().int % 10**7, '07d'),
        )
        db.session.add(patient)
        department = Department(name=f'Perf-{uuid.uuid4().hex[:6]}', name_ar=f'أداء-{uuid.uuid4().hex[:6]}')
        db.session.add(department)
        db.session.commit()
        visit = Visit(
            patient_id=patient.id,
            department_id=department.id,
            status='OPEN',
            payment_status='PENDING',
            visit_type='REGULAR',
        )
        db.session.add(visit)
        db.session.commit()

        login_as(client, u.username, 'super_admin')
        resp = client.get('/super-admin/api/performance')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['visits_today'] is not None
        assert data['visits_today'] >= 1

    def test_performance_page_renders(self, login_as, client, ctx):
        u = ctx.user(role='super_admin')
        login_as(client, u.username, 'super_admin')
        resp = client.get('/super-admin/performance')
        assert resp.status_code == 200
        assert b'cpu-usage' in resp.data
        assert b'memory-usage' in resp.data
        assert b'disk-usage' in resp.data
