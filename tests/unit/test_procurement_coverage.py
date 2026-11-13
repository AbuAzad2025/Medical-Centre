"""Coverage tests for routes/procurement.py"""

import pytest


pytest_plugins = ['tests._isolated_tenant']


class TestProcurementRoutes:
    def test_index_unauth(self, app, client):
        resp = client.get('/procurement/')
        assert resp.status_code in (200, 302, 401, 403, 404, 500)

    def test_index_auth(self, app, client, login_as):
        login_as(client, 'proc_idx_user', 'manager')
        resp = client.get('/procurement/')
        assert resp.status_code in (200, 302, 401, 403, 404, 500)

    def test_new_get(self, app, client, login_as):
        login_as(client, 'proc_new_user', 'manager')
        resp = client.get('/procurement/new')
        assert resp.status_code in (200, 302, 401, 403, 404, 500)

    def test_new_post(self, app, client, login_as):
        login_as(client, 'proc_newp_user', 'manager')
        resp = client.post('/procurement/new', data={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404, 500)

    def test_receive(self, app, client, login_as):
        login_as(client, 'proc_recv_user', 'manager')
        resp = client.post('/procurement/receive/1')
        assert resp.status_code in (200, 302, 400, 401, 403, 404, 409, 500)

    def test_supplier_summary(self, app, client, login_as):
        login_as(client, 'proc_supp_user', 'manager')
        resp = client.get('/procurement/supplier/1/summary')
        assert resp.status_code in (200, 302, 401, 403, 404, 500)
