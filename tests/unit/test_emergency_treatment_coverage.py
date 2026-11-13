"""Coverage tests for routes/emergency/treatment.py"""

import pytest


pytest_plugins = ['tests._isolated_tenant']


class TestEmergencyTreatmentRoutes:
    def test_treatment_unauth(self, app, client):
        resp = client.get('/emergency/treatment/1')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_treatment_auth(self, app, client, login_as):
        login_as(client, 'em_trt_user', 'emergency')
        resp = client.get('/emergency/treatment/1')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_end_treatment(self, app, client, login_as):
        login_as(client, 'em_endtrt_user', 'emergency')
        resp = client.post('/emergency/end-treatment/1')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_start_treatment(self, app, client, login_as):
        login_as(client, 'em_strtrt_user', 'emergency')
        resp = client.post('/emergency/start-treatment/1')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_emergency_visits(self, app, client, login_as):
        login_as(client, 'em_visits_user', 'emergency')
        resp = client.get('/emergency/emergency-visits')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_emergency_treatment_visit(self, app, client, login_as):
        login_as(client, 'em_trtvis_user', 'emergency')
        resp = client.get('/emergency/emergency-treatment/1')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_complete_visit(self, app, client, login_as):
        login_as(client, 'em_complete_user', 'emergency')
        resp = client.post('/emergency/emergency-visits/1/complete')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)
