"""Emergency cases + treatment routes (was 19%/25%)."""

import pytest


@pytest.fixture()
def _emg_client(client, db, test_tenant):
    from tests.tenant_context import ensure_test_user, login_test_client

    u = ensure_test_user(db, test_tenant, username='emg_test', role='emergency')
    login_test_client(client, u, test_tenant)
    return client


class TestEmergencyCases:
    def test_cases_list(self, _emg_client):
        resp = _emg_client.get('/emergency/cases')
        assert resp.status_code in (200, 302)

    def test_cases_dashboard(self, _emg_client):
        resp = _emg_client.get('/emergency/dashboard')
        assert resp.status_code in (200, 302)


class TestEmergencyTreatment:
    def test_treatment_routes_exist(self, app):
        assert 'emergency' in app.blueprints
