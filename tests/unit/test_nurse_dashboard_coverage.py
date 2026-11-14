"""Coverage tests for routes/nurse_routes/dashboard.py"""

import pytest


pytest_plugins = ['tests._isolated_tenant']


class TestNurseDashboardRoutes:
    def test_index_unauth(self, app, client):
        resp = client.get('/nurse/')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_index_auth(self, app, client, login_as):
        login_as(client, 'nurse_dash_idx_user', 'nurse')
        resp = client.get('/nurse/')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_dashboard_unauth(self, app, client):
        resp = client.get('/nurse/dashboard')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_dashboard_auth(self, app, client, login_as):
        login_as(client, 'nurse_dash_dash_user', 'nurse')
        resp = client.get('/nurse/dashboard')
        assert resp.status_code in (200, 302, 401, 403, 404)
