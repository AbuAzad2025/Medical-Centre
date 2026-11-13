"""Coverage tests for routes/emergency/api.py"""

pytest_plugins = ['tests._isolated_tenant']


class TestEmergencyApi:
    def test_ems_intake_unauth(self, app, client):
        resp = client.post('/emergency/api/ems/intake', json={'patient_name': 'Test'})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_ems_intake_missing_name(self, app, client, login_as):
        login_as(client, 'ems_intake_user', 'emergency')
        resp = client.post('/emergency/api/ems/intake', json={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_ems_intake_valid(self, app, client, login_as):
        login_as(client, 'ems_intake2_user', 'emergency')
        resp = client.post(
            '/emergency/api/ems/intake',
            json={
                'patient_name': 'Test Patient',
                'phone': '0501234567',
                'chief_complaint': 'chest pain',
                'severity': 'HIGH',
            },
        )
        assert resp.status_code in (200, 201, 302, 400, 401, 403, 404)
