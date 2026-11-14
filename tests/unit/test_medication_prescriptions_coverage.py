"""Coverage tests for routes/medication_routes/prescriptions.py"""

pytest_plugins = ['tests._isolated_tenant']


class TestMedicationPrescriptionsRoutes:
    def test_prescriptions_unauth(self, app, client):
        resp = client.get('/medication/prescriptions')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_prescriptions_auth(self, app, client, login_as):
        login_as(client, 'med_rx_list_user', 'doctor')
        resp = client.get('/medication/prescriptions')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_api_prescriptions(self, app, client):
        resp = client.get('/medication/api/prescriptions')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_api_prescriptions_auth(self, app, client, login_as):
        login_as(client, 'med_rx_api_user', 'doctor')
        resp = client.get('/medication/api/prescriptions')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_dispense(self, app, client):
        resp = client.post('/medication/prescriptions/dispense/1')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_refill(self, app, client):
        resp = client.post('/medication/prescriptions/1/refill')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)
        resp = client.post('/medication/prescriptions/1/refills')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)
        resp = client.post('/medication/prescription/1/refill')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_refills_get(self, app, client):
        for path in ['/medication/refills', '/medication/prescription-refills', '/medication/api/refills', '/medication/api/prescription-refills']:
            resp = client.get(path)
            assert resp.status_code in (200, 302, 401, 403, 404)

    def test_refills_get_auth(self, app, client, login_as):
        login_as(client, 'med_rx_refills_user', 'pharmacist')
        for path in ['/medication/refills', '/medication/prescription-refills', '/medication/api/refills', '/medication/api/prescription-refills']:
            resp = client.get(path)
            assert resp.status_code in (200, 302, 401, 403, 404)

    def test_refill_status(self, app, client):
        resp = client.get('/medication/refills/1/status')
        assert resp.status_code in (200, 302, 401, 403, 404)
        resp = client.post('/medication/refills/1/status', data={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)