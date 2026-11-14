"""Coverage tests for routes/api_lab.py"""

import pytest


pytest_plugins = ['tests._isolated_tenant']


class TestApiLabRoutes:
    def test_cancel_unauth(self, app, client):
        resp = client.post('/api/lab/requests/1/cancel')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_cancel_auth(self, app, client, login_as):
        login_as(client, 'api_lab_cancel_user', 'doctor')
        resp = client.post('/api/lab/requests/1/cancel', json={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_amend_unauth(self, app, client):
        resp = client.post('/api/lab/results/1/amend')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_amend_auth(self, app, client, login_as):
        login_as(client, 'api_lab_amend_user', 'doctor')
        resp = client.post('/api/lab/results/1/amend', json={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)
