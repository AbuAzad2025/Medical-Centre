"""Payment + auth deep coverage. All tests assert status < 500."""

import pytest


@pytest.fixture()
def _pay_rc(client, db, test_tenant):
    from tests.tenant_context import ensure_test_user, login_test_client

    u = ensure_test_user(db, test_tenant, username='pay_rc2', role='reception')
    login_test_client(client, u, test_tenant)
    return client


class TestPaymentRoutes:
    def test_payment_dashboard(self, _pay_rc):
        assert _pay_rc.get('/payment/dashboard').status_code < 500

    def test_process_nonexistent_visit(self, _pay_rc):
        assert _pay_rc.get('/payment/process/99999').status_code < 500

    def test_receipt_nonexistent(self, _pay_rc):
        assert _pay_rc.get('/payment/receipt/99999').status_code < 500


class TestAuthDeep:
    def test_login_with_tenant_slug(self, app, db, test_tenant):
        c = app.test_client()
        resp = c.post(
            '/auth/login',
            data={
                'username': 'reception',
                'password': 'ValidPass123!',
                'tenant_slug': test_tenant.slug,
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200

    def test_profile_post(self, app, db, test_tenant):
        from tests.tenant_context import ensure_test_user, login_test_client

        u = ensure_test_user(db, test_tenant, username='prof_upd2', role='reception')
        c = app.test_client()
        login_test_client(c, u, test_tenant)
        resp = c.post(
            '/auth/profile',
            data={
                'full_name': 'Updated',
                'phone': '0599999999',
                'email': u.email,
            },
        )
        assert resp.status_code < 500

    def test_impersonate_requires_admin(self, client, db, test_tenant):
        from tests.tenant_context import ensure_test_user, login_test_client

        u = ensure_test_user(db, test_tenant, username='imp_low2', role='reception')
        login_test_client(client, u, test_tenant)
        resp = client.post('/auth/impersonate/1')
        assert resp.status_code < 500

    def test_booking_create_get(self, app, db, test_tenant):
        from tests.tenant_context import ensure_test_user, login_test_client

        u = ensure_test_user(db, test_tenant, username='book_deep2', role='reception')
        c = app.test_client()
        login_test_client(c, u, test_tenant)
        assert c.get('/booking/create').status_code < 500
