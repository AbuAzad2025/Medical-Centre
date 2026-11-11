"""Coverage tests for routes.main.py"""

from __future__ import annotations

import pytest

pytest_plugins = ['tests._isolated_tenant']


class TestMainRoutes:
    def test_index_unauthenticated(self, app, client):
        resp = client.get('/')
        assert resp.status_code in (200, 302)

    def test_health(self, app, client):
        resp = client.get('/health')
        assert resp.status_code in (200, 503)
        data = resp.get_json()
        assert 'status' in data

    def test_api_search_tenants_empty_query(self, app, client):
        resp = client.get('/api/tenants/search')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'tenants' in data

    def test_api_search_tenants_short_query(self, app, client):
        resp = client.get('/api/tenants/search?q=a')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data == {'tenants': []}

    def test_privacy_policy(self, app, client):
        resp = client.get('/privacy-policy')
        assert resp.status_code == 200

    def test_terms_of_use(self, app, client):
        resp = client.get('/terms-of-use')
        assert resp.status_code == 200

    def test_technical_support(self, app, client):
        resp = client.get('/technical-support')
        assert resp.status_code == 200

    def test_about_system(self, app, client):
        resp = client.get('/about-system')
        assert resp.status_code == 200

    def test_set_language_ar(self, app, client):
        resp = client.get('/set-language/ar')
        assert resp.status_code in (302, 200)

    def test_set_language_en(self, app, client):
        resp = client.get('/set-language/en')
        assert resp.status_code in (302, 200)

    def test_set_language_invalid(self, app, client):
        resp = client.get('/set-language/xx')
        assert resp.status_code in (302, 200)

    def test_api_search_authenticated(self, app, client, login_as):
        login_as(client, 'main_search_user', 'doctor')
        resp = client.get('/api/search')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'success'

    def test_dashboard_authenticated(self, app, client, login_as):
        login_as(client, 'main_dashboard_user', 'doctor')
        resp = client.get('/dashboard')
        assert resp.status_code in (200, 302)

    def test_package_restricted_authenticated(self, app, client, login_as):
        login_as(client, 'main_pkg_user', 'doctor')
        resp = client.get('/package-restricted')
        assert resp.status_code in (200, 302)

    def test_appointments_redirect_doctor(self, app, client, login_as):
        login_as(client, 'main_apt_doc', 'doctor')
        resp = client.get('/appointments')
        assert resp.status_code in (302, 200)

    def test_appointments_redirect_reception(self, app, client, login_as):
        login_as(client, 'main_apt_rec', 'reception')
        resp = client.get('/appointments')
        assert resp.status_code in (302, 200)

    def test_appointments_redirect_patient(self, app, client, login_as):
        login_as(client, 'main_apt_pat', 'patient')
        resp = client.get('/appointments')
        assert resp.status_code in (302, 200)

    def test_settings_authenticated(self, app, client, login_as):
        login_as(client, 'main_settings_user', 'manager')
        resp = client.get('/settings')
        assert resp.status_code in (200, 302)
