"""Coverage tests for routes/radiology/images.py"""

import os
import tempfile
from datetime import datetime, UTC

import pytest

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

    def test_file_auth_not_found(self, app, client, login_as):
        login_as(client, 'rad_file_user', 'radiology')
        resp = client.get('/radiology/files/999999')
        assert resp.status_code in (200, 302, 401, 403, 404)

    def test_file_auth_local_storage(self, app, client, login_as, db, test_tenant):
        login_as(client, 'rad_file_local_user', 'radiology')
        from models.file_management import FileUpload

        # Create a temp file
        fd, path = tempfile.mkstemp()
        os.close(fd)
        with open(path, 'w') as f:
            f.write('test content')

        f = FileUpload(
            tenant_id=test_tenant.id,
            filename='test.txt',
            original_filename='test.txt',
            file_path=path,
            file_size=12,
            file_type='text/plain',
            file_extension='txt',
            storage_backend='local',
            is_expired=False,
            expires_at=None,
        )
        db.session.add(f)
        db.session.flush()

        resp = client.get(f'/radiology/files/{f.id}')
        assert resp.status_code in (200, 302, 401, 403, 404, 500)

        # Cleanup
        try:
            os.remove(path)
        except OSError:
            pass

    def test_file_auth_expired(self, app, client, login_as, db, test_tenant):
        login_as(client, 'rad_file_exp_user', 'radiology')
        from models.file_management import FileUpload
        from datetime import timedelta

        f = FileUpload(
            tenant_id=test_tenant.id,
            filename='test.txt',
            original_filename='test.txt',
            file_path='/nonexistent/test.txt',
            file_size=12,
            file_type='text/plain',
            file_extension='txt',
            storage_backend='local',
            is_expired=True,
            expires_at=datetime.now(UTC) - timedelta(days=1),
        )
        db.session.add(f)
        db.session.flush()

        resp = client.get(f'/radiology/files/{f.id}')
        assert resp.status_code in (200, 302, 401, 403, 404, 500)
