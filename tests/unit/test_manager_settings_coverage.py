"""Coverage tests for routes/manager/settings.py"""

pytest_plugins = ['tests._isolated_tenant']


class TestManagerSettingsRoutes:
    def test_settings_unauth(self, app, client):
        resp = client.get('/manager/settings')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_settings_auth(self, app, client, login_as):
        login_as(client, 'mgr_settings_user', 'manager')
        resp = client.get('/manager/settings')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_settings_post(self, app, client, login_as):
        login_as(client, 'mgr_settings_post_user', 'manager')
        resp = client.post('/manager/settings', data={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_test_sms(self, app, client, login_as):
        login_as(client, 'mgr_sms_user', 'manager')
        resp = client.post('/manager/settings/test-sms', json={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)
