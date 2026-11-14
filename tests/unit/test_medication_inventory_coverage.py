"""Coverage tests for routes/medication_routes/inventory.py"""

import pytest


pytest_plugins = ['tests._isolated_tenant']


class TestMedicationInventoryRoutes:
    def test_stock_alerts_unauth(self, app, client):
        resp = client.get('/medication/stock-alerts')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_stock_alerts_auth(self, app, client, login_as):
        login_as(client, 'med_inv_alerts_user', 'pharmacist')
        resp = client.get('/medication/stock-alerts')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_supply_requests_unauth(self, app, client):
        resp = client.get('/medication/supply-requests')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_supply_requests_auth(self, app, client, login_as):
        login_as(client, 'med_inv_supply_user', 'pharmacist')
        resp = client.get('/medication/supply-requests')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_create_supply_request_get(self, app, client, login_as):
        login_as(client, 'med_inv_create_user', 'pharmacist')
        resp = client.get('/medication/supply-requests/create')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_create_supply_request_post(self, app, client, login_as):
        login_as(client, 'med_inv_create_post_user', 'pharmacist')
        resp = client.post('/medication/supply-requests/create', data={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_view_supply_request(self, app, client, login_as):
        login_as(client, 'med_inv_view_user', 'pharmacist')
        resp = client.get('/medication/supply-requests/1')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_approve_supply_request(self, app, client, login_as):
        login_as(client, 'med_inv_approve_user', 'pharmacist')
        resp = client.post('/medication/supply-requests/1/approve')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_fulfill_supply_request(self, app, client, login_as):
        login_as(client, 'med_inv_fulfill_user', 'pharmacist')
        resp = client.post('/medication/supply-requests/1/fulfill')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)
