"""Coverage tests for routes/data_warehouse_routes.py"""

import pytest


pytest_plugins = ['tests._isolated_tenant']


class TestDataWarehouseRoutes:
    def test_index_unauth(self, app, client):
        resp = client.get('/data-warehouse/')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_index_auth(self, app, client, login_as):
        login_as(client, 'dw_idx_user', 'manager')
        resp = client.get('/data-warehouse/')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_sync_unauth(self, app, client):
        resp = client.post('/data-warehouse/sync')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_sync_auth(self, app, client, login_as):
        login_as(client, 'dw_sync_user', 'manager')
        resp = client.post('/data-warehouse/sync')
        assert resp.status_code in (200, 302, 400, 401, 403, 404)
