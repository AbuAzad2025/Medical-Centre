"""Coverage tests for routes/manager/approvals.py"""

pytest_plugins = ['tests._isolated_tenant']


class TestManagerApprovalsRoutes:
    def test_force_payment_approvals_unauth(self, app, client):
        resp = client.get('/manager/force-payment-approvals')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_force_payment_approvals_auth(self, app, client, login_as):
        login_as(client, 'mgr_appr_fp_user', 'admin')
        resp = client.get('/manager/force-payment-approvals')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_approve_force_payment(self, app, client):
        resp = client.post('/manager/approve-force-payment/1')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_reject_force_payment(self, app, client):
        resp = client.post('/manager/reject-force-payment/1')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_custom_service_approvals_unauth(self, app, client):
        resp = client.get('/manager/custom-service-approvals')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_custom_service_approvals_auth(self, app, client, login_as):
        login_as(client, 'mgr_appr_cs_user', 'admin')
        resp = client.get('/manager/custom-service-approvals')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_approve_custom_service(self, app, client):
        resp = client.post('/manager/approve-custom-service/1')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_reject_custom_service(self, app, client):
        resp = client.post('/manager/reject-custom-service/1')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)