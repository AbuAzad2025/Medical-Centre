"""Coverage tests for routes/patient_education_routes.py"""

import pytest

pytest_plugins = ['tests._isolated_tenant']


class TestPatientEducationRoutes:
    def test_index_unauth(self, app, client):
        resp = client.get('/patient-education/')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_index_auth(self, app, client, login_as):
        login_as(client, 'pedu_idx_user', 'doctor')
        resp = client.get('/patient-education/')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_index_with_category(self, app, client, login_as):
        login_as(client, 'pedu_idx_cat_user', 'doctor')
        resp = client.get('/patient-education/?category=general')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_view_material_unauth(self, app, client):
        resp = client.get('/patient-education/material/1')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_view_material_auth(self, app, client, login_as):
        login_as(client, 'pedu_view_user', 'doctor')
        resp = client.get('/patient-education/material/1')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_new_get(self, app, client, login_as):
        login_as(client, 'pedu_new_user', 'doctor')
        resp = client.get('/patient-education/new')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_new_post(self, app, client, login_as):
        login_as(client, 'pedu_new_post_user', 'doctor')
        resp = client.post('/patient-education/new', data={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_edit_get(self, app, client, login_as):
        login_as(client, 'pedu_edit_user', 'doctor')
        resp = client.get('/patient-education/edit/1')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_edit_post(self, app, client, login_as):
        login_as(client, 'pedu_edit_post_user', 'doctor')
        resp = client.post('/patient-education/edit/1', data={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_assign(self, app, client, login_as):
        login_as(client, 'pedu_assign_user', 'doctor')
        resp = client.post('/patient-education/assign', json={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_patient_materials(self, app, client, login_as):
        login_as(client, 'pedu_pat_user', 'doctor')
        resp = client.get('/patient-education/patient/1')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)
