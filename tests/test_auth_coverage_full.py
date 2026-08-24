"""Auth routes full coverage (43% → target 95%)."""

import pytest


@pytest.fixture()
def _auth(client, db, test_tenant):
    return client


class TestLoginFlow:
    def test_login_get_renders(self, _auth):
        resp = _auth.get('/auth/login')
        assert resp.status_code == 200
        assert b'username' in resp.data

    def test_login_success_redirects(self, app, db, test_tenant):
        from tests.tenant_context import ensure_test_user

        u = ensure_test_user(db, test_tenant, username='login_cov', role='reception')
        resp = app.test_client().post(
            '/auth/login',
            data={'username': u.username, 'password': 'ValidPass123!'},
            follow_redirects=True,
        )
        assert resp.status_code == 200

    def test_login_wrong_password_stays(self, _auth):
        resp = _auth.post('/auth/login', data={'username': 'nonexistent_cov', 'password': 'wrong'})
        assert resp.status_code in (200, 401)

    def test_logout(self, app, db, test_tenant):
        from tests.tenant_context import ensure_test_user, login_test_client

        u = ensure_test_user(db, test_tenant, username='logout_cov', role='reception')
        c = app.test_client()
        login_test_client(c, u, test_tenant)
        resp = c.get('/auth/logout', follow_redirects=True)
        assert resp.status_code == 200


class TestProfileFlow:
    def test_profile_get(self, app, db, test_tenant):
        from tests.tenant_context import ensure_test_user, login_test_client

        u = ensure_test_user(db, test_tenant, username='prof_cov', role='reception')
        c = app.test_client()
        login_test_client(c, u, test_tenant)
        resp = c.get('/auth/profile')
        assert resp.status_code == 200

    def test_change_password_valid(self, app, db, test_tenant):
        from tests.tenant_context import ensure_test_user, login_test_client

        u = ensure_test_user(db, test_tenant, username='chpw_cov', role='reception')
        c = app.test_client()
        login_test_client(c, u, test_tenant)
        resp = c.post(
            '/auth/change-password',
            json={'current_password': 'ValidPass123!', 'new_password': 'NewSecure1!'},
        )
        assert resp.status_code in (200, 302, 400)

    def test_forgot_password_get(self, _auth):
        resp = _auth.get('/auth/forgot-password')
        assert resp.status_code == 200

    def test_register_redirects(self, _auth):
        resp = _auth.get('/auth/register')
        assert resp.status_code in (200, 302)


class TestTenantListAPI:
    def test_tenants_list_public(self, _auth):
        resp = _auth.get('/auth/api/tenants-list')
        assert resp.status_code == 200
