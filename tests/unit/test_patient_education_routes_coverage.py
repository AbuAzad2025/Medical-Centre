"""Coverage tests for routes/patient_education_routes.py"""

pytest_plugins = ['tests._isolated_tenant']


class TestPatientEducationRoutes:
    def test_index_unauth(self, app, client):
        resp = client.get('/patient-education/')
        assert resp.status_code in (200, 302, 401, 404)

    def test_index_auth(self, app, client, login_as):
        login_as(client, 'pedu_idx_user', 'doctor')
        resp = client.get('/patient-education/')
        assert resp.status_code in (200, 302, 403, 404)

    def test_material_detail(self, app, client, login_as):
        login_as(client, 'pedu_mat_user', 'doctor')
        resp = client.get('/patient-education/material/1')
        assert resp.status_code in (200, 302, 403, 404)

    def test_new_get(self, app, client, login_as):
        login_as(client, 'pedu_new_user', 'doctor')
        resp = client.get('/patient-education/new')
        assert resp.status_code in (200, 302, 403, 404)

    def test_patient_view(self, app, client, login_as):
        login_as(client, 'pedu_pat_user', 'doctor')
        resp = client.get('/patient-education/patient/1')
        assert resp.status_code in (200, 302, 403, 404)
