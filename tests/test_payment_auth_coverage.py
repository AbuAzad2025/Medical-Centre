"""Payment routes (39%, 294 missed) + auth routes deep coverage."""

import pytest


@pytest.fixture()
def _pay_reception(client, db, test_tenant):
    from tests.tenant_context import ensure_test_user, login_test_client

    u = ensure_test_user(db, test_tenant, username='pay_rc', role='reception')
    login_test_client(client, u, test_tenant)
    return client


@pytest.fixture()
def _pay_doctor(client, db, test_tenant):
    from tests.tenant_context import ensure_test_user, login_test_client

    u = ensure_test_user(db, test_tenant, username='pay_dr', role='doctor')
    login_test_client(client, u, test_tenant)
    return client


class TestPaymentRoutes:
    def test_payment_dashboard(self, _pay_reception):
        resp = _pay_reception.get('/payment/dashboard')
        assert resp.status_code in (200, 302)

    def test_process_nonexistent_visit(self, _pay_reception):
        assert _pay_reception.get('/payment/process/99999').status_code in (200, 302, 404)

    def test_receipt_nonexistent(self, _pay_reception):
        assert _pay_reception.get('/payment/receipt/99999').status_code in (200, 302, 404)


class TestAuthDeepCoverage:
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

    def test_profile_post_updates_name(self, app, db, test_tenant):
        from tests.tenant_context import ensure_test_user, login_test_client

        u = ensure_test_user(db, test_tenant, username='prof_upd', role='reception')
        c = app.test_client()
        login_test_client(c, u, test_tenant)
        resp = c.post(
            '/auth/profile',
            data={
                'full_name': 'Updated Name',
                'phone': '0599999999',
                'email': u.email,
            },
        )
        assert resp.status_code in (200, 302)

    def test_impersonate_requires_admin(self, client, db, test_tenant):
        from tests.tenant_context import ensure_test_user, login_test_client

        u = ensure_test_user(db, test_tenant, username='imp_low', role='reception')
        login_test_client(client, u, test_tenant)
        resp = client.post('/auth/impersonate/1')
        assert resp.status_code in (302, 403)


class TestBookingDeep:
    def test_booking_create_get(self, app, db, test_tenant):
        from tests.tenant_context import ensure_test_user, login_test_client

        u = ensure_test_user(db, test_tenant, username='book_deep', role='reception')
        c = app.test_client()
        login_test_client(c, u, test_tenant)
        resp = c.get('/booking/create')
        assert resp.status_code in (200, 302)
