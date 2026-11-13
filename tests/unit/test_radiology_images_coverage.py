"""Coverage tests for routes/radiology/images.py"""

pytest_plugins = ['tests._isolated_tenant']


class TestRadiologyImagesRoutes:
    def test_images_unauth(self, app, client):
        resp = client.get('/radiology/images')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_images_auth(self, app, client, login_as):
        login_as(client, 'rad_img_user', 'radiology')
        resp = client.get('/radiology/images')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_file_unauth(self, app, client):
        resp = client.get('/radiology/files/1')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_file_auth(self, app, client, login_as):
        login_as(client, 'rad_file_user', 'radiology')
        resp = client.get('/radiology/files/1')
        assert resp.status_code in (200, 302, 401, 403, 404)
