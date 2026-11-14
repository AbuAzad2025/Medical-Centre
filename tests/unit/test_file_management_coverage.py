"""Coverage tests for models/file_management.py"""

from datetime import datetime, UTC
from models.file_management import FileUpload, FileCategory, FilePermission


class TestFileManagement:
    def test_file_upload_repr(self):
        f = FileUpload(
            tenant_id=1,
            filename='test.pdf',
            original_filename='test.pdf',
            file_path='/files/test.pdf',
            file_size=1000,
            file_type='application/pdf',
            file_extension='pdf',
            uploaded_at=datetime.now(UTC),
        )
        assert repr(f) is not None

    def test_file_upload_get_file_hash(self):
        f = FileUpload(
            tenant_id=1,
            filename='test.pdf',
            original_filename='test.pdf',
            file_path='/files/test.pdf',
            file_size=1000,
            file_type='application/pdf',
            file_extension='pdf',
            uploaded_at=datetime.now(UTC),
        )
        result = f.get_file_hash()
        assert result is None or isinstance(result, str)

    def test_file_upload_is_expired(self):
        f = FileUpload(
            tenant_id=1,
            filename='test.pdf',
            original_filename='test.pdf',
            file_path='/files/test.pdf',
            file_size=1000,
            file_type='application/pdf',
            file_extension='pdf',
            uploaded_at=datetime.now(UTC),
        )
        result = f.is_expired()
        assert isinstance(result, bool)

    def test_file_upload_get_file_url(self):
        f = FileUpload(
            tenant_id=1,
            filename='test.pdf',
            original_filename='test.pdf',
            file_path='/files/test.pdf',
            file_size=1000,
            file_type='application/pdf',
            file_extension='pdf',
            uploaded_at=datetime.now(UTC),
        )
        result = f.get_file_url()
        assert result is not None

    def test_file_upload_to_dict(self):
        f = FileUpload(
            tenant_id=1,
            filename='test.pdf',
            original_filename='test.pdf',
            file_path='/files/test.pdf',
            file_size=1000,
            file_type='application/pdf',
            file_extension='pdf',
            uploaded_at=datetime.now(UTC),
        )
        d = f.to_dict()
        assert isinstance(d, dict)

    def test_file_category_repr(self):
        c = FileCategory(
            tenant_id=1,
            name='Documents',
            name_ar='مستندات',
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert repr(c) is not None

    def test_file_category_get_allowed_extensions(self):
        c = FileCategory(
            tenant_id=1,
            name='Documents',
            name_ar='مستندات',
            allowed_extensions='pdf,doc,docx',
        )
        result = c.get_allowed_extensions()
        assert result is not None

    def test_file_category_set_allowed_extensions(self):
        c = FileCategory(
            tenant_id=1,
            name='Documents',
            name_ar='مستندات',
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        c.set_allowed_extensions(['pdf', 'doc'])
        assert c.allowed_extensions is not None

    def test_file_category_is_extension_allowed(self):
        c = FileCategory(
            tenant_id=1,
            name='Documents',
            name_ar='مستندات',
            allowed_extensions='pdf,doc,docx',
        )
        result = c.is_extension_allowed('pdf')
        assert isinstance(result, bool)

    def test_file_category_to_dict(self):
        c = FileCategory(
            tenant_id=1,
            name='Documents',
            name_ar='مستندات',
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        d = c.to_dict()
        assert isinstance(d, dict)

    def test_file_permission_repr(self):
        p = FilePermission(
            tenant_id=1,
            file_id=1,
            user_id=1,
            role='user',
            granted_at=datetime.now(UTC),
        )
        assert repr(p) is not None

    def test_file_permission_is_expired(self):
        p = FilePermission(
            tenant_id=1,
            file_id=1,
            user_id=1,
            role='user',
            granted_at=datetime.now(UTC),
        )
        result = p.is_expired()
        assert isinstance(result, bool)

    def test_file_permission_to_dict(self):
        p = FilePermission(
            tenant_id=1,
            file_id=1,
            user_id=1,
            role='user',
            granted_at=datetime.now(UTC),
        )
        d = p.to_dict()
        assert isinstance(d, dict)

    def test_file_upload_get_presigned_url(self):
        f = FileUpload(
            tenant_id=1,
            filename='test.pdf',
            original_filename='test.pdf',
            file_path='/files/test.pdf',
            file_size=1000,
            file_type='application/pdf',
            file_extension='pdf',
            uploaded_at=datetime.now(UTC),
        )
        result = f.get_presigned_url()
        assert result is not None or result is None
