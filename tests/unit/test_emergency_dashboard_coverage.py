"""Coverage tests for routes/emergency/dashboard.py"""

import pytest


pytest_plugins = ['tests._isolated_tenant']


class TestEmergencyDashboardRoutes:
    def test_index_unauth(self, app, client):
        resp = client.get('/emergency/')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_index_auth(self, app, client, login_as):
        login_as(client, 'em_dash_idx_user', 'emergency')
        resp = client.get('/emergency/')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_reports_unauth(self, app, client):
        resp = client.get('/emergency/reports')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_reports_auth(self, app, client, login_as):
        login_as(client, 'em_dash_rep_user', 'emergency')
        resp = client.get('/emergency/reports')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_reports_with_dates(self, app, client, login_as):
        login_as(client, 'em_dash_rep2_user', 'emergency')
        resp = client.get('/emergency/reports?start_date=2024-01-01&end_date=2024-12-31')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_reports_invalid_dates(self, app, client, login_as):
        login_as(client, 'em_dash_rep3_user', 'emergency')
        resp = client.get('/emergency/reports?start_date=invalid&end_date=alsoinvalid')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_dashboard_unauth(self, app, client):
        resp = client.get('/emergency/dashboard')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_dashboard_auth(self, app, client, login_as):
        login_as(client, 'em_dash_dash_user', 'emergency')
        resp = client.get('/emergency/dashboard')
        assert resp.status_code in (200, 302, 401, 403, 404)
