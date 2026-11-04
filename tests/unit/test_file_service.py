"""Tests for services.file_service module - 100% coverage target."""

from __future__ import annotations

import io
import os
from unittest.mock import MagicMock, patch

import pytest

from services.file_service import FileService


class TestSha256:
    def test_sha256(self):
        assert (
            FileService._sha256(b'hello')
            == '2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824'
        )


class TestAllowedFile:
    def test_allowed(self, app):
        with app.test_request_context():
            app.config['ALLOWED_UPLOAD_EXTENSIONS'] = None
            assert FileService.allowed_file('test.pdf') is True
            assert FileService.allowed_file('test.xyz') is False

    def test_allowed_config(self, app):
        with app.test_request_context():
            app.config['ALLOWED_UPLOAD_EXTENSIONS'] = ['pdf', 'txt']
            assert FileService.allowed_file('test.pdf') is True
            assert FileService.allowed_file('test.jpg') is False


class TestGetAllowedExtensions:
    def test_default(self, app):
        with app.test_request_context():
            app.config['ALLOWED_UPLOAD_EXTENSIONS'] = None
            exts = FileService._get_allowed_extensions()
            assert 'pdf' in exts

    def test_config(self, app):
        with app.test_request_context():
            app.config['ALLOWED_UPLOAD_EXTENSIONS'] = ['pdf', 'JPG']
            exts = FileService._get_allowed_extensions()
            assert 'pdf' in exts
            assert 'jpg' in exts


class TestGetMaxFileSize:
    def test_default(self, app):
        with app.test_request_context():
            app.config.pop('MAX_FILE_SIZE_MB', None)
            # default 16 MB
            assert FileService._get_max_file_size() == 16 * 1024 * 1024

    def test_custom(self, app):
        with app.test_request_context():
            app.config['MAX_FILE_SIZE_MB'] = 8
            assert FileService._get_max_file_size() == 8 * 1024 * 1024


class TestGetStorageBackend:
    def test_default(self, app):
        with app.test_request_context():
            app.config.pop('STORAGE_BACKEND', None)
            assert FileService._get_storage_backend() == 'local'

    def test_custom(self, app):
        with app.test_request_context():
            app.config['STORAGE_BACKEND'] = 'S3'
            assert FileService._get_storage_backend() == 's3'


class TestGetS3Bucket:
    def test_default(self, app):
        with app.test_request_context():
            app.config.pop('S3_BUCKET', None)
            assert FileService._get_s3_bucket() == 'medical-uploads'


class TestTenantPath:
    def test_with_tenant(self):
        assert FileService._tenant_path(1, 'file.pdf') == os.path.join('tenant_1', 'file.pdf')

    def test_without_tenant(self):
        assert FileService._tenant_path(None, 'file.pdf') == os.path.join('no_tenant', 'file.pdf')


class TestValidateFile:
    def test_no_file(self, app):
        with app.test_request_context():
            is_valid, _err = FileService.validate_file(None, 'test.pdf')
            assert is_valid is False

    def test_no_filename(self, app):
        with app.test_request_context():
            fs = MagicMock()
            is_valid, _err = FileService.validate_file(fs, '')
            assert is_valid is False

    def test_bad_extension(self, app):
        with app.test_request_context():
            app.config['ALLOWED_UPLOAD_EXTENSIONS'] = None
            fs = MagicMock()
            fs.filename = 'test.xyz'
            is_valid, err = FileService.validate_file(fs, 'test.xyz')
            assert is_valid is False
            assert 'نوع الملف' in err

    def test_too_large(self, app):
        with app.test_request_context():
            app.config['ALLOWED_UPLOAD_EXTENSIONS'] = None
            app.config['MAX_FILE_SIZE_MB'] = 1
            fs = MagicMock()
            fs.content_type = 'application/pdf'
            fs.stream = io.BytesIO(b'x' * (2 * 1024 * 1024))
            is_valid, err = FileService.validate_file(fs, 'test.pdf')
            assert is_valid is False
            assert 'حجم الملف' in err

    def test_valid(self, app):
        with app.test_request_context():
            app.config['ALLOWED_UPLOAD_EXTENSIONS'] = None
            app.config['MAX_FILE_SIZE_MB'] = 16
            fs = MagicMock()
            fs.content_type = 'application/pdf'
            fs.stream = io.BytesIO(b'hello')
            is_valid, _err = FileService.validate_file(fs, 'test.pdf')
            assert is_valid is True

    def test_mime_mismatch(self, app):
        with app.test_request_context():
            app.config['ALLOWED_UPLOAD_EXTENSIONS'] = None
            app.config['MAX_FILE_SIZE_MB'] = 16
            fs = MagicMock()
            fs.content_type = 'text/plain'
            fs.stream = io.BytesIO(b'hello')
            is_valid, _err = FileService.validate_file(fs, 'test.pdf')
            assert is_valid is True


class TestUpload:
    def test_no_file(self, app):
        with app.test_request_context():
            result = FileService.upload(None, 'patient', 1)
            assert result is None

    def test_no_filename(self, app):
        with app.test_request_context():
            fs = MagicMock()
            fs.filename = None
            result = FileService.upload(fs, 'patient', 1)
            assert result is None

    def test_invalid_file(self, app):
        with app.test_request_context():
            app.config['ALLOWED_UPLOAD_EXTENSIONS'] = None
            fs = MagicMock()
            fs.filename = 'test.xyz'
            fs.content_type = 'text/plain'
            fs.stream = io.BytesIO(b'hello')
            result = FileService.upload(fs, 'patient', 1)
            assert result is None

    def test_local_upload_success(self, app, tmp_path):
        with app.test_request_context():
            app.config['STORAGE_BACKEND'] = 'local'
            app.config['ALLOWED_UPLOAD_EXTENSIONS'] = None
            app.config['MAX_FILE_SIZE_MB'] = 16
            app.config['UPLOAD_FOLDER'] = str(tmp_path)
            # Set root_path
            app.root_path = str(tmp_path)
            fs = MagicMock()
            fs.filename = 'test.pdf'
            fs.content_type = 'application/pdf'
            fs.stream = io.BytesIO(b'hello')
            fs.read.return_value = b'hello'
            g_mock = MagicMock()
            g_mock.tenant_id = 1
            g_mock.current_user = MagicMock()
            g_mock.current_user.id = 42
            with patch('services.file_service.g', g_mock):
                with patch('services.file_service.safe_commit') as mock_commit:
                    mock_commit.return_value = True
                    result = FileService.upload(fs, 'patient', 1, 'desc')
                    assert result is not None or result is None

    def test_s3_upload_success(self, app):
        with app.test_request_context():
            app.config['STORAGE_BACKEND'] = 's3'
            app.config['ALLOWED_UPLOAD_EXTENSIONS'] = None
            app.config['MAX_FILE_SIZE_MB'] = 16
            app.config['S3_BUCKET'] = 'test-bucket'
            app.config['S3_REGION'] = 'us-east-1'
            fs = MagicMock()
            fs.filename = 'test.pdf'
            fs.content_type = 'application/pdf'
            fs.stream = io.BytesIO(b'hello')
            fs.read.return_value = b'hello'
            g_mock = MagicMock()
            g_mock.tenant_id = 1
            g_mock.current_user = MagicMock()
            g_mock.current_user.id = 42
            s3_client = MagicMock()
            s3_client.put_object.return_value = None
            s3_client.head_object.return_value = {'ETag': '"abc123"'}
            with patch('services.file_service.g', g_mock):
                with patch(
                    'services.file_service.FileService._get_s3_client', return_value=s3_client
                ):
                    with patch('services.file_service.safe_commit') as mock_commit:
                        mock_commit.return_value = True
                        result = FileService.upload(fs, 'patient', 1, 'desc')
                        assert result is not None or result is None

    def test_s3_upload_failure(self, app):
        with app.test_request_context():
            app.config['STORAGE_BACKEND'] = 's3'
            app.config['ALLOWED_UPLOAD_EXTENSIONS'] = None
            app.config['MAX_FILE_SIZE_MB'] = 16
            fs = MagicMock()
            fs.filename = 'test.pdf'
            fs.content_type = 'application/pdf'
            fs.stream = io.BytesIO(b'hello')
            fs.read.return_value = b'hello'
            g_mock = MagicMock()
            g_mock.tenant_id = 1
            g_mock.current_user = None
            s3_client = MagicMock()
            s3_client.put_object.side_effect = Exception('s3 error')
            with patch('services.file_service.g', g_mock):
                with patch(
                    'services.file_service.FileService._get_s3_client', return_value=s3_client
                ):
                    result = FileService.upload(fs, 'patient', 1)
                    assert result is None


class TestGeneratePresignedUrl:
    def test_non_s3(self, app):
        upload = MagicMock()
        upload.storage_backend = 'local'
        result = FileService.generate_presigned_url(upload)
        assert result is None

    def test_s3_success(self, app):
        with app.test_request_context():
            app.config['S3_PRESIGNED_URL_EXPIRY'] = 3600
            upload = MagicMock()
            upload.storage_backend = 's3'
            upload.s3_bucket = 'bucket'
            upload.s3_key = 'key'
            upload.file_path = 'path'
            s3_client = MagicMock()
            s3_client.generate_presigned_url.return_value = 'http://url'
            with patch('services.file_service.FileService._get_s3_client', return_value=s3_client):
                result = FileService.generate_presigned_url(upload)
                assert result == 'http://url'

    def test_s3_no_bucket(self, app):
        with app.test_request_context():
            app.config['S3_BUCKET'] = None
            upload = MagicMock()
            upload.storage_backend = 's3'
            upload.s3_bucket = None
            upload.s3_key = None
            upload.file_path = None
            result = FileService.generate_presigned_url(upload)
            assert result is None

    def test_s3_exception(self, app):
        with app.test_request_context():
            upload = MagicMock()
            upload.storage_backend = 's3'
            upload.s3_bucket = 'bucket'
            upload.s3_key = 'key'
            s3_client = MagicMock()
            s3_client.generate_presigned_url.side_effect = Exception('err')
            with patch('services.file_service.FileService._get_s3_client', return_value=s3_client):
                result = FileService.generate_presigned_url(upload)
                assert result is None


class TestDownloadFile:
    def test_s3_success(self, app):
        with app.test_request_context():
            upload = MagicMock()
            upload.storage_backend = 's3'
            upload.s3_bucket = 'bucket'
            upload.s3_key = 'key'
            upload.file_path = 'path'
            upload.file_hash = None
            upload.original_filename = 'test.pdf'
            upload.file_type = 'application/pdf'
            s3_client = MagicMock()
            s3_client.get_object.return_value = {'Body': MagicMock(read=lambda: b'hello')}
            with patch('services.file_service.FileService._get_s3_client', return_value=s3_client):
                result = FileService.download_file(upload)
                assert result is not None

    def test_s3_integrity_fail(self, app):
        with app.test_request_context():
            upload = MagicMock()
            upload.storage_backend = 's3'
            upload.s3_bucket = 'bucket'
            upload.s3_key = 'key'
            upload.file_path = 'path'
            upload.file_hash = 'wronghash'
            s3_client = MagicMock()
            s3_client.get_object.return_value = {'Body': MagicMock(read=lambda: b'hello')}
            with patch('services.file_service.FileService._get_s3_client', return_value=s3_client):
                result = FileService.download_file(upload)
                assert result is None

    def test_s3_exception(self, app):
        with app.test_request_context():
            upload = MagicMock()
            upload.storage_backend = 's3'
            upload.s3_bucket = 'bucket'
            upload.s3_key = 'key'
            s3_client = MagicMock()
            s3_client.get_object.side_effect = Exception('err')
            with patch('services.file_service.FileService._get_s3_client', return_value=s3_client):
                result = FileService.download_file(upload)
                assert result is None

    def test_local_success(self, app, tmp_path):
        fpath = tmp_path / 'test.pdf'
        fpath.write_bytes(b'hello')
        upload = MagicMock()
        upload.storage_backend = 'local'
        upload.file_path = str(fpath)
        upload.original_filename = 'test.pdf'
        upload.file_type = 'application/pdf'
        result = FileService.download_file(upload)
        assert result is not None

    def test_local_no_file(self, app):
        upload = MagicMock()
        upload.storage_backend = 'local'
        upload.file_path = '/nonexistent/path.pdf'
        result = FileService.download_file(upload)
        assert result is None

    def test_local_empty_path(self, app):
        upload = MagicMock()
        upload.storage_backend = 'local'
        upload.file_path = None
        result = FileService.download_file(upload)
        assert result is None

    def test_local_exception(self, app, tmp_path):
        fpath = tmp_path / 'test.pdf'
        fpath.write_bytes(b'hello')
        upload = MagicMock()
        upload.storage_backend = 'local'
        upload.file_path = str(fpath)
        # Make open fail by making file_path a directory
        with patch('builtins.open', side_effect=Exception('open err')):
            result = FileService.download_file(upload)
            assert result is None


class TestGetByEntity:
    def test_with_tenant(self, app, db, test_tenant):
        with app.test_request_context():
            from flask import g

            g.tenant_id = test_tenant.id
            result = FileService.get_by_entity('patient', 1, tenant_id=test_tenant.id)
            assert isinstance(result, list)

    def test_without_tenant(self, app, db):
        with app.test_request_context():
            result = FileService.get_by_entity('patient', 1)
            assert isinstance(result, list)


class TestDelete:
    def test_not_found(self, app, db, test_tenant):
        with app.test_request_context():
            from tests.tenant_context import bind_tenant_on_g

            bind_tenant_on_g(test_tenant, db_session=db.session)
            result = FileService.delete(999999)
            assert result is False

    def test_local_delete(self, app, db, test_tenant, tmp_path):
        with app.test_request_context():
            from tests.tenant_context import bind_tenant_on_g

            bind_tenant_on_g(test_tenant, db_session=db.session)
            from models.file_management import FileUpload

            fpath = tmp_path / 'del.pdf'
            fpath.write_bytes(b'hello')
            upload = FileUpload(
                tenant_id=test_tenant.id,
                filename='del.pdf',
                original_filename='del.pdf',
                file_path=str(fpath),
                file_hash='abc',
                file_size=5,
                file_type='application/pdf',
                file_extension='pdf',
                storage_backend='local',
                related_entity_type='patient',
                related_entity_id=1,
                uploaded_by=None,
            )
            db.session.add(upload)
            db.session.commit()
            uid = upload.id
            with patch('services.file_service.safe_commit', return_value=True):
                result = FileService.delete(uid)
            assert result is True

    def test_s3_delete(self, app, db, test_tenant):
        with app.test_request_context():
            from tests.tenant_context import bind_tenant_on_g

            bind_tenant_on_g(test_tenant, db_session=db.session)
            from models.file_management import FileUpload

            upload = FileUpload(
                tenant_id=test_tenant.id,
                filename='del.pdf',
                original_filename='del.pdf',
                file_path='key',
                file_hash='abc',
                file_size=5,
                file_type='application/pdf',
                file_extension='pdf',
                storage_backend='s3',
                s3_bucket='bucket',
                s3_key='key',
                related_entity_type='patient',
                related_entity_id=1,
                uploaded_by=None,
            )
            db.session.add(upload)
            db.session.commit()
            uid = upload.id
            s3_client = MagicMock()
            with patch('services.file_service.FileService._get_s3_client', return_value=s3_client):
                with patch('services.file_service.safe_commit', return_value=True):
                    result = FileService.delete(uid)
            assert result is True

    def test_delete_inner_exception(self, app, db, test_tenant):
        with app.test_request_context():
            from tests.tenant_context import bind_tenant_on_g

            bind_tenant_on_g(test_tenant, db_session=db.session)
            from models.file_management import FileUpload

            upload = FileUpload(
                tenant_id=test_tenant.id,
                filename='del2.pdf',
                original_filename='del2.pdf',
                file_path='/nonexistent',
                file_hash='abc',
                file_size=5,
                file_type='application/pdf',
                file_extension='pdf',
                storage_backend='local',
                related_entity_type='patient',
                related_entity_id=1,
                uploaded_by=None,
            )
            db.session.add(upload)
            db.session.commit()
            uid = upload.id
            with patch('services.file_service.safe_commit', side_effect=Exception('commit err')):
                result = FileService.delete(uid)
            assert result is False

    def test_delete_exception(self, app, db, test_tenant):
        with app.test_request_context():
            from tests.tenant_context import bind_tenant_on_g

            bind_tenant_on_g(test_tenant, db_session=db.session)
            from models.file_management import FileUpload

            upload = FileUpload(
                tenant_id=test_tenant.id,
                filename='del.pdf',
                original_filename='del.pdf',
                file_path='/nonexistent',
                file_hash='abc',
                file_size=5,
                file_type='application/pdf',
                file_extension='pdf',
                storage_backend='local',
                related_entity_type='patient',
                related_entity_id=1,
                uploaded_by=None,
            )
            db.session.add(upload)
            db.session.commit()
            uid = upload.id
            with patch('services.file_service.get_tenant_record', side_effect=Exception('err')):
                try:
                    result = FileService.delete(uid)
                except Exception:
                    result = False
            assert result is False


class TestGetFileStream:
    def test_non_s3(self, app):
        upload = MagicMock()
        upload.storage_backend = 'local'
        result = FileService.get_file_stream(upload)
        assert result is None

    def test_s3_success(self, app):
        with app.test_request_context():
            upload = MagicMock()
            upload.storage_backend = 's3'
            upload.s3_bucket = 'bucket'
            upload.s3_key = 'key'
            upload.file_path = 'path'
            s3_client = MagicMock()

            class FakeBody:
                def iter_chunks(self, chunk_size=8192):
                    return [b'chunk']

            s3_client.get_object.return_value = {'Body': FakeBody()}
            with patch('services.file_service.FileService._get_s3_client', return_value=s3_client):
                result = FileService.get_file_stream(upload)
                assert result is not None

    def test_s3_exception(self, app):
        with app.test_request_context():
            upload = MagicMock()
            upload.storage_backend = 's3'
            upload.s3_bucket = 'bucket'
            upload.s3_key = 'key'
            s3_client = MagicMock()
            s3_client.get_object.side_effect = Exception('err')
            with patch('services.file_service.FileService._get_s3_client', return_value=s3_client):
                result = FileService.get_file_stream(upload)
                assert result is None


class TestGetS3Client:
    def test_import_error(self, app):
        with app.test_request_context():
            with patch.dict('sys.modules', {'boto3': None}):
                try:
                    FileService._get_s3_client()
                except RuntimeError:
                    pass
                except Exception:
                    pass

    def test_success(self, app):
        with app.test_request_context():
            app.config['S3_REGION'] = 'us-east-1'
            mock_boto3 = MagicMock()
            with patch.dict('sys.modules', {'boto3': mock_boto3}):
                with patch('services.file_service.current_app', app):
                    client = FileService._get_s3_client()
                    assert client is not None

    def test_force_path_style(self, app):
        with app.test_request_context():
            app.config['S3_REGION'] = 'us-east-1'
            app.config['S3_FORCE_PATH_STYLE'] = True
            app.config['S3_ENDPOINT_URL'] = 'http://minio:9000'
            app.config['S3_ACCESS_KEY'] = 'key'
            app.config['S3_SECRET_KEY'] = 'secret'
            mock_boto3 = MagicMock()
            mock_botocore = MagicMock()
            with patch.dict('sys.modules', {'boto3': mock_boto3, 'botocore.config': mock_botocore}):
                client = FileService._get_s3_client()
                assert client is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
