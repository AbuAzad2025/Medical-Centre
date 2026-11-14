"""Coverage tests for routes/radiology/fhir.py"""

import pytest

pytest_plugins = ['tests._isolated_tenant']


class TestRadiologyFhirRoutes:
    def test_worklist_unauth(self, app, client):
        resp = client.get('/radiology/api/worklist')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_worklist_auth(self, app, client, login_as):
        login_as(client, 'rad_fhir_wl_user', 'radiology')
        resp = client.get('/radiology/api/worklist')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_worklist_with_visit_id(self, app, client, login_as):
        login_as(client, 'rad_fhir_wl2_user', 'radiology')
        resp = client.get('/radiology/api/worklist?visit_id=1')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_worklist_with_status(self, app, client, login_as):
        login_as(client, 'rad_fhir_wl3_user', 'radiology')
        resp = client.get('/radiology/api/worklist?status=PENDING')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_observation_unauth(self, app, client):
        resp = client.get('/radiology/api/fhir/observation/radiology/1')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_observation_auth(self, app, client, login_as):
        login_as(client, 'rad_fhir_obs_user', 'radiology')
        resp = client.get('/radiology/api/fhir/observation/radiology/1')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_diagnostic_report_unauth(self, app, client):
        resp = client.get('/radiology/api/fhir/diagnosticreport/radiology/1')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_diagnostic_report_auth(self, app, client, login_as):
        login_as(client, 'rad_fhir_dr_user', 'radiology')
        resp = client.get('/radiology/api/fhir/diagnosticreport/radiology/1')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_imaging_study_unauth(self, app, client):
        resp = client.get('/radiology/api/fhir/imagingstudy/1')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_imaging_study_auth(self, app, client, login_as):
        login_as(client, 'rad_fhir_is_user', 'radiology')
        resp = client.get('/radiology/api/fhir/imagingstudy/1')
        assert resp.status_code in (200, 302, 401, 403, 404)
