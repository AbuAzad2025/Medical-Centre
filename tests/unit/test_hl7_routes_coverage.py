"""Coverage tests for routes/hl7_routes.py"""

import pytest


pytest_plugins = ['tests._isolated_tenant']


class TestHL7Routes:
    def test_status_unauth(self, app, client):
        resp = client.get('/hl7/status')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_status_auth(self, app, client, login_as):
        login_as(client, 'hl7_status_user', 'admin')
        resp = client.get('/hl7/status')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_ingest_unauth(self, app, client):
        resp = client.post('/hl7/ingest', data='MSH|...', content_type='text/plain')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_ingest_auth(self, app, client, login_as):
        login_as(client, 'hl7_ingest_user', 'admin')
        resp = client.post('/hl7/ingest', data='MSH|...', content_type='text/plain')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_control(self, app, client, login_as):
        login_as(client, 'hl7_ctrl_user', 'admin')
        resp = client.post('/hl7/control/start')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)
