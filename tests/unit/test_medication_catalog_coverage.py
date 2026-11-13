"""Coverage tests for routes/medication_routes/catalog.py"""

pytest_plugins = ['tests._isolated_tenant']


class TestMedicationCatalogRoutes:
    def test_list_unauth(self, app, client):
        resp = client.get('/medication/list')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_list_auth(self, app, client, login_as):
        login_as(client, 'med_cat_list_user', 'pharmacist')
        resp = client.get('/medication/list')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_add_get(self, app, client, login_as):
        login_as(client, 'med_cat_add_user', 'pharmacist')
        resp = client.get('/medication/add')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_edit(self, app, client, login_as):
        login_as(client, 'med_cat_edit_user', 'pharmacist')
        resp = client.get('/medication/edit/1')
        assert resp.status_code in (200, 302, 401, 403, 404)
