"""Manager + super_admin route smoke tests (was <40%)."""

import pytest


@pytest.fixture()
def _admin_client(client, db, test_tenant):
    from tests.tenant_context import ensure_test_user, login_test_client

    u = ensure_test_user(db, test_tenant, username='sa_test', role='super_admin')
    login_test_client(client, u, test_tenant)
    return client


@pytest.fixture()
def _mgr_client(client, db, test_tenant):
    from tests.tenant_context import ensure_test_user, login_test_client

    u = ensure_test_user(db, test_tenant, username='mgr_cov', role='manager')
    login_test_client(client, u, test_tenant)
    return client


class TestManagerRoutes:
    def test_manager_dashboard(self, _mgr_client):
        resp = _mgr_client.get('/manager/dashboard')
        assert resp.status_code in (200, 302)

    def test_manager_financial(self, _mgr_client):
        resp = _mgr_client.get('/manager/financial')
        assert resp.status_code in (200, 302)

    def test_manager_reports(self, _mgr_client):
        resp = _mgr_client.get('/manager/reports')
        assert resp.status_code in (200, 302)

    def test_manager_pricing(self, _mgr_client):
        resp = _mgr_client.get('/manager/pricing')
        assert resp.status_code in (200, 302)


class TestSuperAdminRoutes:
    def test_sa_dashboard(self, _admin_client):
        resp = _admin_client.get('/super-admin/dashboard')
        assert resp.status_code in (200, 302)

    def test_sa_users(self, _admin_client):
        resp = _admin_client.get('/super-admin/users')
        assert resp.status_code in (200, 302)

    def test_sa_departments(self, _admin_client):
        resp = _admin_client.get('/super-admin/departments')
        assert resp.status_code in (200, 302)

    def test_sa_services(self, _admin_client):
        resp = _admin_client.get('/super-admin/services')
        assert resp.status_code in (200, 302)

    def test_sa_roles(self, _admin_client):
        resp = _admin_client.get('/super-admin/roles')
        assert resp.status_code in (200, 302)
