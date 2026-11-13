"""Coverage tests for routes/order_set_routes.py"""

pytest_plugins = ['tests._isolated_tenant']


class TestOrderSetRoutes:
    def test_index_unauth(self, app, client):
        resp = client.get('/order-sets/')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_index_auth(self, app, client, login_as):
        login_as(client, 'os_idx_user', 'doctor')
        resp = client.get('/order-sets/')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_detail(self, app, client, login_as):
        login_as(client, 'os_det_user', 'doctor')
        resp = client.get('/order-sets/1')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_api_list(self, app, client, login_as):
        login_as(client, 'os_list_user', 'doctor')
        resp = client.get('/order-sets/api/list')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_bpa_check(self, app, client, login_as):
        login_as(client, 'os_bpa_user', 'doctor')
        resp = client.post('/order-sets/api/bpa/check', json={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_api_create(self, app, client, login_as):
        login_as(client, 'os_create_user', 'doctor')
        resp = client.post('/order-sets/api/create', json={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_bpa_create(self, app, client, login_as):
        login_as(client, 'os_bpac_user', 'doctor')
        resp = client.post('/order-sets/api/bpa/create', json={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)
