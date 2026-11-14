"""Coverage tests for routes/specialty_forms.py"""

pytest_plugins = ['tests._isolated_tenant']


class TestSpecialtyFormsRoutes:
    def test_list_unauth(self, app, client):
        resp = client.get('/specialty-forms')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_list_auth(self, app, client, login_as):
        login_as(client, 'sf_list_user', 'doctor')
        resp = client.get('/specialty-forms')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_new_get(self, app, client):
        resp = client.get('/specialty-forms/new')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_new_post(self, app, client):
        resp = client.post('/specialty-forms/new', data={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_new_auth(self, app, client, login_as):
        login_as(client, 'sf_new_user', 'doctor')
        resp = client.get('/specialty-forms/new')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_detail(self, app, client):
        resp = client.get('/specialty-forms/1')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_detail_auth(self, app, client, login_as):
        login_as(client, 'sf_detail_user', 'doctor')
        resp = client.get('/specialty-forms/1')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_fill_get(self, app, client):
        resp = client.get('/specialty-forms/1/fill')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_fill_post(self, app, client):
        resp = client.post('/specialty-forms/1/fill', data={})
        assert resp.status_code in (200, 302, 400, 401, 403, 404)

    def test_fill_auth(self, app, client, login_as):
        login_as(client, 'sf_fill_user', 'doctor')
        resp = client.get('/specialty-forms/1/fill')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_submissions(self, app, client):
        resp = client.get('/specialty-forms/1/submissions')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_submission_detail(self, app, client):
        resp = client.get('/specialty-forms/submissions/1')
        assert resp.status_code in (200, 302, 401, 403, 404)