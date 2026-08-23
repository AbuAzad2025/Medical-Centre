"""Smoke tests for ai_imaging, dicom, and telemedicine modules.

Verifies routes exist, blueprints register correctly, and key views
return valid HTTP responses when accessed by authorized users.
"""

import pytest


@pytest.fixture()
def _module_client(client, db, test_tenant):
    """Authenticated client with all test modules enabled."""
    from tests.tenant_context import login_test_client, ensure_test_user

    user = ensure_test_user(db, test_tenant, username='modules_test', role='admin')
    login_test_client(client, user, test_tenant)
    return client


class TestAIModuleRoutes:
    """ai_imaging blueprint — route accessibility."""

    def test_ai_imaging_index(self, _module_client):
        resp = _module_client.get('/ai-imaging/')
        assert resp.status_code in (200, 302)

    def test_ai_imaging_blueprint_registered(self, app):
        assert 'ai_imaging' in app.blueprints


class TestDicomModuleRoutes:
    """dicom blueprint — route accessibility."""

    def test_dicom_studies_list(self, _module_client):
        resp = _module_client.get('/dicom/studies')
        assert resp.status_code in (200, 302)

    def test_dicom_blueprint_registered(self, app):
        assert 'dicom' in app.blueprints


class TestTelemedicineModuleRoutes:
    """telemedicine blueprint — route accessibility."""

    def test_telemedicine_index(self, _module_client):
        resp = _module_client.get('/telemedicine/')
        assert resp.status_code in (200, 302)

    def test_telemedicine_new(self, _module_client):
        resp = _module_client.get('/telemedicine/new')
        assert resp.status_code in (200, 302)

    def test_telemedicine_blueprint_registered(self, app):
        assert 'telemedicine' in app.blueprints
