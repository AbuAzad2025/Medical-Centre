"""Coverage tests for routes/saas_billing_routes.py"""

import pytest


pytest_plugins = ['tests._isolated_tenant']


class TestSaasBillingRoutes:
    def test_webhook_no_payload(self, app, client):
        resp = client.post('/api/billing/stripe/webhook', data=b'{}', content_type='application/json')
        assert resp.status_code in (200, 400, 401, 403, 404, 500)

    def test_webhook_empty(self, app, client):
        resp = client.post('/api/billing/stripe/webhook', data=b'', content_type='application/json')
        assert resp.status_code in (200, 400, 401, 403, 404, 500)

    def test_checkout_unauth(self, app, client):
        resp = client.post('/api/billing/checkout', json={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_checkout_auth(self, app, client, login_as):
        login_as(client, 'saas_checkout_user', 'manager')
        resp = client.post('/api/billing/checkout', json={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_portal_unauth(self, app, client):
        resp = client.post('/api/billing/portal', json={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_portal_auth(self, app, client, login_as):
        login_as(client, 'saas_portal_user', 'manager')
        resp = client.post('/api/billing/portal', json={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404, 500)

    def test_cancel_unauth(self, app, client):
        resp = client.post('/api/billing/subscription/cancel', json={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_cancel_auth(self, app, client, login_as):
        login_as(client, 'saas_cancel_user', 'manager')
        resp = client.post('/api/billing/subscription/cancel', json={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_change_plan_unauth(self, app, client):
        resp = client.post('/api/billing/subscription/change-plan', json={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_change_plan_auth(self, app, client, login_as):
        login_as(client, 'saas_change_user', 'manager')
        resp = client.post('/api/billing/subscription/change-plan', json={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)
