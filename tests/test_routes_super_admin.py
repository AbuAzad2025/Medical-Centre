"""HTTP route tests for the super_admin blueprint."""

import types
import uuid

import pytest

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
            first_name=kw.get('first_name', 'سوبر'),
            last_name=kw.get('last_name', 'أدمن'),
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


def _make_superadmin(login_as, client, ctx):
    u = ctx.user(role='super_admin')
    login_as(client, u.username, 'super_admin')
    return u


class TestSuperAdminDashboard:
    def test_dashboard_renders(self, login_as, client, ctx):
        _make_superadmin(login_as, client, ctx)
        resp = client.get('/super-admin/dashboard')
        assert resp.status_code in (200, 302)


class TestSuperAdminUsers:
    def test_users_list(self, login_as, client, ctx):
        _make_superadmin(login_as, client, ctx)
        resp = client.get('/super-admin/users')
        assert resp.status_code in (200, 302)

    def test_users_create_get(self, login_as, client, ctx):
        _make_superadmin(login_as, client, ctx)
        resp = client.get('/super-admin/users/create')
        assert resp.status_code in (200, 302)

    def test_users_create_post(self, login_as, client, ctx):
        _make_superadmin(login_as, client, ctx)
        resp = client.post(
            '/super-admin/users/create',
            data={
                'username': f'newusr_{uuid.uuid4().hex[:6]}',
                'email': f'{uuid.uuid4().hex[:8]}@test.local',
                'full_name': 'مستخدم جديد',
                'password': 'TestPass123!',
                'role': 'doctor',
                'is_active': 'y',
            },
        )
        assert resp.status_code in (302, 200)

    def test_users_edit_get(self, login_as, client, ctx):
        _make_superadmin(login_as, client, ctx)
        u = ctx.user(role='doctor')
        resp = client.get(f'/super-admin/users/{u.id}/edit')
        assert resp.status_code in (200, 302)

    def test_users_delete_post(self, login_as, client, ctx):
        _make_superadmin(login_as, client, ctx)
        u = ctx.user(role='doctor')
        resp = client.post(f'/super-admin/users/{u.id}/delete')
        assert resp.status_code in (302, 200)

    def test_users_reset_password(self, login_as, client, ctx):
        _make_superadmin(login_as, client, ctx)
        u = ctx.user(role='doctor')
        resp = client.post(
            f'/super-admin/users/{u.id}/reset-password',
            data={'new_password': 'NewPass123!'},
        )
        assert resp.status_code in (302, 200)


class TestSuperAdminRoles:
    def test_roles_list(self, login_as, client, ctx):
        _make_superadmin(login_as, client, ctx)
        resp = client.get('/super-admin/roles')
        assert resp.status_code in (200, 302)

    def test_roles_create_get(self, login_as, client, ctx):
        _make_superadmin(login_as, client, ctx)
        resp = client.get('/super-admin/roles/create')
        assert resp.status_code in (200, 302)

    def test_roles_create_post(self, login_as, client, ctx):
        _make_superadmin(login_as, client, ctx)
        resp = client.post(
            '/super-admin/roles/create',
            data={
                'name': f'role_{uuid.uuid4().hex[:6]}',
                'description': 'دور اختبار',
                'base_role': 'doctor',
            },
        )
        assert resp.status_code in (302, 200)

    def test_roles_edit_get(self, login_as, client, ctx):
        _make_superadmin(login_as, client, ctx)
        resp = client.get('/super-admin/roles/1/edit')
        assert resp.status_code in (200, 302)

    def test_permissions_matrix(self, login_as, client, ctx):
        _make_superadmin(login_as, client, ctx)
        resp = client.get('/super-admin/permissions-matrix')
        assert resp.status_code in (200, 302)

    def test_permissions_list(self, login_as, client, ctx):
        _make_superadmin(login_as, client, ctx)
        resp = client.get('/super-admin/permissions')
        assert resp.status_code in (200, 302)


class TestSuperAdminServices:
    def test_services_list(self, login_as, client, ctx):
        _make_superadmin(login_as, client, ctx)
        resp = client.get('/super-admin/services')
        assert resp.status_code in (200, 302)

    def test_services_create_post(self, login_as, client, ctx):
        _make_superadmin(login_as, client, ctx)
        resp = client.post(
            '/super-admin/services/create',
            data={
                'name': f'svc_{uuid.uuid4().hex[:6]}',
                'name_ar': 'خدمة اختبار',
                'price': '100',
                'department_id': str(ctx.department().id),
            },
        )
        assert resp.status_code in (302, 200)

    def test_pricing_page(self, login_as, client, ctx):
        _make_superadmin(login_as, client, ctx)
        resp = client.get('/super-admin/pricing')
        assert resp.status_code in (200, 302)


class TestSuperAdminDepartments:
    def test_departments_list(self, login_as, client, ctx):
        _make_superadmin(login_as, client, ctx)
        resp = client.get('/super-admin/departments')
        assert resp.status_code in (200, 302)

    def test_departments_create_post(self, login_as, client, ctx):
        _make_superadmin(login_as, client, ctx)
        tag = uuid.uuid4().hex[:6]
        resp = client.post(
            '/super-admin/departments/create',
            data={'name': f'Dept-{tag}', 'name_ar': f'قسم-{tag}'},
        )
        assert resp.status_code in (302, 200)

    def test_edit_department_get(self, login_as, client, ctx):
        _make_superadmin(login_as, client, ctx)
        d = ctx.department()
        resp = client.get(f'/super-admin/edit-department/{d.id}')
        assert resp.status_code in (200, 302)

    def test_activate_deactivate_department(self, login_as, client, ctx):
        _make_superadmin(login_as, client, ctx)
        d = ctx.department()
        resp = client.post(f'/super-admin/activate-department/{d.id}')
        assert resp.status_code in (302, 200)
        resp = client.post(f'/super-admin/deactivate-department/{d.id}')
        assert resp.status_code in (302, 200)


class TestSuperAdminAnalytics:
    def test_analytics_page(self, login_as, client, ctx):
        _make_superadmin(login_as, client, ctx)
        resp = client.get('/super-admin/analytics')
        assert resp.status_code in (200, 302)

    def test_reports_page(self, login_as, client, ctx):
        _make_superadmin(login_as, client, ctx)
        resp = client.get('/super-admin/reports')
        assert resp.status_code in (200, 302)

    def test_performance_page(self, login_as, client, ctx):
        _make_superadmin(login_as, client, ctx)
        resp = client.get('/super-admin/performance')
        assert resp.status_code in (200, 302)


class TestSuperAdminSystem:
    def test_system_page(self, login_as, client, ctx):
        _make_superadmin(login_as, client, ctx)
        resp = client.get('/super-admin/system')
        assert resp.status_code in (200, 302)

    def test_system_config_get(self, login_as, client, ctx):
        _make_superadmin(login_as, client, ctx)
        resp = client.get('/super-admin/system-config')
        assert resp.status_code in (200, 302)

    def test_system_config_post(self, login_as, client, ctx):
        _make_superadmin(login_as, client, ctx)
        resp = client.post(
            '/super-admin/system-config',
            data={'hospital_name': 'Test Hospital'},
        )
        assert resp.status_code in (302, 200)


class TestSuperAdminBackup:
    def test_backup_page(self, login_as, client, ctx):
        _make_superadmin(login_as, client, ctx)
        resp = client.get('/super-admin/backup')
        assert resp.status_code in (200, 302)

    def test_backup_history(self, login_as, client, ctx):
        _make_superadmin(login_as, client, ctx)
        resp = client.get('/super-admin/backup/history')
        assert resp.status_code in (200, 302)


class TestSuperAdminData:
    def test_export_data(self, login_as, client, ctx):
        _make_superadmin(login_as, client, ctx)
        resp = client.post(
            '/super-admin/export-data',
            data={'export_type': 'patients'},
        )
        assert resp.status_code in (302, 200)

    def test_data_warehouse(self, login_as, client, ctx):
        _make_superadmin(login_as, client, ctx)
        resp = client.get('/super-admin/data-warehouse')
        assert resp.status_code in (200, 302)


class TestSuperAdminSecurity:
    def test_security_logs(self, login_as, client, ctx):
        _make_superadmin(login_as, client, ctx)
        resp = client.get('/super-admin/security-logs')
        assert resp.status_code in (200, 302)

    def test_audit_trail(self, login_as, client, ctx):
        _make_superadmin(login_as, client, ctx)
        resp = client.get('/super-admin/audit-trail')
        assert resp.status_code in (200, 302)
