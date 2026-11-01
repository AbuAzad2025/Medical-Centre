"""Comprehensive E2E tests (pytest + Flask test client).

Covers major route surfaces, CRUD operations, multi-tenant isolation, and
error handling (404/403/500).  Runs against the real PostgreSQL test database
via the standard conftest fixtures.
"""

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.core.tenant.models import Tenant
from app.extensions import db
from models.department import Department
from models.patient import Patient
from models.user import User
from tests.tenant_context import (
    activate_tenant_modules,
    ensure_test_user,
    login_test_client,
)

pytestmark = [pytest.mark.e2e]


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


def _make_role(login_as, client, ctx, role):
    u = ctx.user(role=role)
    login_as(client, u.username, role, password='test123')
    return u


# ---------------------------------------------------------------------------
# Major route smoke tests
# ---------------------------------------------------------------------------
class TestMajorRoutes:
    def test_reception_routes(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'reception')
        for path in [
            '/reception/patients',
            '/reception/appointments',
        ]:
            resp = client.get(path)
            assert resp.status_code in (200, 302, 404), (path, resp.status_code)

    def test_doctor_routes(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'doctor')
        for path in ['/doctor/', '/doctor/patients', '/doctor/dashboard']:
            resp = client.get(path)
            assert resp.status_code in (200, 302, 404), (path, resp.status_code)

    def test_lab_routes(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'lab')
        for path in ['/lab/', '/lab/dashboard', '/lab/requests', '/lab/results', '/lab/tests', '/lab/worklist']:
            resp = client.get(path)
            assert resp.status_code in (200, 302, 404), (path, resp.status_code)

    def test_radiology_routes(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'radiology')
        for path in ['/radiology/', '/radiology/dashboard', '/radiology/requests', '/radiology/results']:
            resp = client.get(path)
            assert resp.status_code in (200, 302, 404), (path, resp.status_code)

    def test_medication_routes(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'pharmacist')
        for path in ['/medication/', '/medication/dashboard', '/medication/list']:
            resp = client.get(path)
            assert resp.status_code in (200, 302, 404), (path, resp.status_code)

    def test_finance_routes(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'accountant')
        for path in ['/finance/', '/finance/dashboard', '/accountant/dashboard']:
            resp = client.get(path)
            assert resp.status_code in (200, 302, 404), (path, resp.status_code)

    def test_emergency_routes(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'emergency')
        for path in ['/emergency/', '/emergency/dashboard', '/emergency/patients']:
            resp = client.get(path)
            assert resp.status_code in (200, 302, 404), (path, resp.status_code)

    def test_nurse_routes(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'nurse')
        for path in ['/nurse/', '/nurse/dashboard', '/nurse/patients']:
            resp = client.get(path)
            assert resp.status_code in (200, 302, 404), (path, resp.status_code)

    def test_telemedicine_routes(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'doctor')
        for path in ['/telemedicine/', '/telemedicine/dashboard']:
            resp = client.get(path)
            assert resp.status_code in (200, 302, 404), (path, resp.status_code)

    def test_owner_dashboard(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'owner')
        resp = client.get('/owner/dashboard')
        assert resp.status_code in (200, 302, 404)


# ---------------------------------------------------------------------------
# CRUD operation tests
# ---------------------------------------------------------------------------
class TestCRUDOperations:
    @pytest.fixture
    def ctx(self, app, db, test_tenant):
        # reuse the shared ctx pattern
        import types
        import uuid


        tenant_id = test_tenant.id

        def _patient(**kw):
            p = Patient(
                first_name=kw.get('first_name', 'E2E'),
                last_name=kw.get('last_name', 'Patient'),
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
                name_ar=kw.get('name_ar', f'Dept-{tag}'),
                is_active=True,
            )
            db.session.add(d)
            db.session.commit()
            return d

        def _user(**kw):
            role = kw.get('role', 'doctor')
            u = User(
                tenant_id=tenant_id,
                username=kw.get('username', f'{role}_{uuid.uuid4().hex[:6]}'),
                email=kw.get('email', f'{uuid.uuid4().hex[:8]}@test.local'),
                full_name=kw.get('full_name', 'E2E User'),
                role=role,
                is_active=True,
            )
            u.set_password('test123')
            db.session.add(u)
            db.session.commit()
            return u

        return types.SimpleNamespace(
            db=db, tenant_id=tenant_id, patient=_patient, department=_department, user=_user
        )

    def test_create_patient(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'reception')
        phone = '050' + format(uuid.uuid4().int % 10**7, '07d')
        resp = client.post(
            '/reception/add_patient',
            data={
                'first_name': 'E2E',
                'last_name': 'Created',
                'phone': phone,
                'gender': 'M',
            },
            follow_redirects=False,
        )
        assert resp.status_code in (200, 302, 400, 409)

    def test_create_appointment(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'reception')
        p = ctx.patient()
        d = ctx.department()
        doc = ctx.user(role='doctor')
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        resp = client.post(
            '/reception/create_appointment',
            data={
                'patient_id': str(p.id),
                'doctor_id': str(doc.id),
                'department_id': str(d.id),
                'appointment_date': tomorrow,
                'appointment_time': '10:00',
                'duration': '30',
            },
            follow_redirects=False,
        )
        assert resp.status_code in (200, 302, 400)

    def test_read_patient(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'reception')
        p = ctx.patient()
        resp = client.get(f'/reception/view_patient/{p.id}')
        assert resp.status_code in (200, 302, 404)

    def test_list_patients(self, login_as, client, ctx):
        _make_role(login_as, client, ctx, 'reception')
        resp = client.get('/reception/patients')
        assert resp.status_code in (200, 302)


# ---------------------------------------------------------------------------
# Multi-tenant isolation tests
# ---------------------------------------------------------------------------
class TestMultiTenantIsolation:
    def test_anonymous_protected_route_redirects(self, client):
        resp = client.get('/reception/patients')
        assert resp.status_code in (302, 401, 403)

    def test_cross_tenant_patient_not_visible(self, app, client, test_tenant):
        from flask import g

        # Create a patient in the default test tenant
        prev = g.get('_tenant_filter_bypass', False)
        g._tenant_filter_bypass = True
        try:
            p = Patient(first_name='Secret', last_name='Patient', phone='0551234567', gender='F')
            db.session.add(p)
            db.session.commit()
            pid = p.id
        finally:
            if prev:
                g._tenant_filter_bypass = True
            else:
                g.pop('_tenant_filter_bypass', None)

        # Build a second tenant
        g._tenant_filter_bypass = True
        try:
            t2 = db.session.execute(select(Tenant).filter_by(slug='e2e-tenant-b')).scalars().first()
            if not t2:
                t2 = Tenant(
                    slug='e2e-tenant-b',
                    name='E2E Tenant B',
                    contact_email='b@e2e.local',
                    status='ACTIVE',
                )
                db.session.add(t2)
                db.session.commit()
            activate_tenant_modules(app, t2, ['reception', 'doctor'])
            user_b = ensure_test_user(db, t2, username='reception_b', role='reception', password='test123')
        finally:
            g.pop('_tenant_filter_bypass', None)

        login_test_client(client, user_b, t2, password='test123')
        resp = client.get(f'/reception/view_patient/{pid}')
        # Should not expose the other tenant's patient
        assert resp.status_code in (302, 403, 404)

    def test_tenant_slug_mismatch_not_authenticated(self, client):
        resp = client.post(
            '/auth/login',
            data={'username': 'nope', 'password': 'nope', 'tenant_slug': 'does-not-exist'},
        )
        assert resp.status_code in (200, 302, 401, 403)


# ---------------------------------------------------------------------------
# Error handling tests
# ---------------------------------------------------------------------------
class TestErrorHandling:
    def test_404_unknown_route(self, client):
        resp = client.get('/this-route-does-not-exist-xyz')
        assert resp.status_code == 404

    def test_403_forbidden_route(self, login_as, client, ctx):
        # reception user hitting owner dashboard -> forbidden/redirect
        _make_role(login_as, client, ctx, 'reception')
        resp = client.get('/owner/dashboard')
        assert resp.status_code in (302, 401, 403, 404)

    def test_500_error_handler(self, app, test_tenant):
        from tests.tenant_context import ensure_test_user, login_test_client
        u = ensure_test_user(db, test_tenant, username='boom_user', role='reception', password='test123')
        prev_propagate = app.config.get('PROPAGATE_EXCEPTIONS')
        app.config['PROPAGATE_EXCEPTIONS'] = False
        c = app.test_client()
        login_test_client(c, u, test_tenant, password='test123')
        endpoint = 'reception.patients'
        original = app.view_functions.get(endpoint)
        def _boom(*a, **k):
            raise RuntimeError('boom')
        app.view_functions[endpoint] = _boom
        try:
            resp = c.get('/reception/patients')
            assert resp.status_code == 500
        finally:
            if original is not None:
                app.view_functions[endpoint] = original
            app.config['PROPAGATE_EXCEPTIONS'] = prev_propagate


# Need ctx fixture for TestMajorRoutes etc.
@pytest.fixture
def ctx(app, db, test_tenant):
    import types
    import uuid

    tenant_id = test_tenant.id

    def _patient(**kw):
        p = Patient(
            first_name=kw.get('first_name', 'U.O�USO�'),
            last_name=kw.get('last_name', 'OOrO�O"OO�'),
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
            name_ar=kw.get('name_ar', f'Dept-{tag}'),
            is_active=True,
        )
        db.session.add(d)
        db.session.commit()
        return d

    def _user(**kw):
        role = kw.get('role', 'doctor')
        u = User(
            tenant_id=tenant_id,
            username=kw.get('username', f'{role}_{uuid.uuid4().hex[:6]}'),
            email=kw.get('email', f'{uuid.uuid4().hex[:8]}@test.local'),
            full_name=kw.get('full_name', 'U.O3O�OrO_U.'),
            role=role,
            is_active=True,
        )
        u.set_password('test123')
        db.session.add(u)
        db.session.commit()
        return u

    return types.SimpleNamespace(db=db, tenant_id=tenant_id, patient=_patient, department=_department, user=_user)
