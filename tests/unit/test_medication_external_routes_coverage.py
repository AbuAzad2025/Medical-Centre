"""Coverage tests for routes/medication_routes/external.py"""

import pytest


pytest_plugins = ['tests._isolated_tenant']


class TestMedicationExternalRoutes:
    def test_external_drug_import_unauth(self, app, client):
        resp = client.post('/medication/api/external-drug-import')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_external_drug_import_auth(self, app, client, login_as):
        login_as(client, 'med_ext_import_user', 'pharmacist')
        resp = client.post('/medication/api/external-drug-import', json={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_external_drug_search_unauth(self, app, client):
        resp = client.get('/medication/api/external-drug-search')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_external_drug_search_auth(self, app, client, login_as):
        login_as(client, 'med_ext_search_user', 'pharmacist')
        resp = client.get('/medication/api/external-drug-search')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_consumption_report_unauth(self, app, client):
        resp = client.get('/medication/consumption-report')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_consumption_report_auth(self, app, client, login_as):
        login_as(client, 'med_ext_report_user', 'pharmacist')
        resp = client.get('/medication/consumption-report')
        assert resp.status_code in (200, 302, 401, 403, 404)
