"""Coverage tests for routes.radiology.images.py"""

from __future__ import annotations

import pytest

pytest_plugins = ['tests._isolated_tenant']


class TestRadiologyImages:
    def test_images_redirect(self, app, client, login_as):
        login_as(client, 'rad_img_user', 'radiology')
        resp = client.get('/radiology/images')
        assert resp.status_code in (302, 200)

    def test_download_file_not_found(self, app, client, login_as):
        login_as(client, 'rad_dl_user', 'radiology')
        resp = client.get('/radiology/files/99999')
        assert resp.status_code in (302, 200)

    def test_images_redirect_doctor(self, app, client, login_as):
        login_as(client, 'rad_img_doc', 'doctor')
        resp = client.get('/radiology/images')
        assert resp.status_code in (302, 200, 403)

    def test_download_file_manager(self, app, client, login_as):
        login_as(client, 'rad_dl_mgr', 'manager')
        resp = client.get('/radiology/files/99999')
        assert resp.status_code in (302, 200)
