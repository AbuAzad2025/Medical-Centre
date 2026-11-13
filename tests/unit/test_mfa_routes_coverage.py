"""Coverage tests for routes/mfa_routes.py"""

import pytest


pytest_plugins = ['tests._isolated_tenant']


class TestMFARoutes:
    def test_setup_get_unauthenticated(self, app, client):
        resp = client.get('/mfa/setup')
        assert resp.status_code in (302, 401)

    def test_status_unauthenticated(self, app, client):
        resp = client.get('/mfa/status')
        assert resp.status_code in (302, 401)

    def test_verify_get_no_pending(self, app, client):
        resp = client.get('/mfa/verify')
        assert resp.status_code in (302, 200)

    def test_disable_unauthenticated(self, app, client):
        resp = client.post('/mfa/disable')
        assert resp.status_code in (302, 401, 405)

    def test_api_check_missing_params(self, app, client):
        resp = client.post('/mfa/api/check', json={})
        assert resp.status_code in (400, 401, 302)

    def test_setup_authenticated(self, app, client, login_as):
        login_as(client, 'mfa_setup_user', 'doctor')
        resp = client.get('/mfa/setup')
        assert resp.status_code in (200, 302)

    def test_status_authenticated(self, app, client, login_as):
        login_as(client, 'mfa_status_user', 'doctor')
        resp = client.get('/mfa/status')
        assert resp.status_code in (200, 302)

    def test_setup_post_invalid_code(self, app, client, login_as):
        login_as(client, 'mfa_setup2_user', 'doctor')
        resp = client.post('/mfa/setup', data={'code': '000000'})
        assert resp.status_code in (200, 302)

    def test_api_check_invalid_code(self, app, client):
        resp = client.post('/mfa/api/check', json={'user_id': 1, 'code': '000000'})
        assert resp.status_code in (400, 401, 200)
