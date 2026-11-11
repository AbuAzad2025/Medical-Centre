"""Coverage tests for services.dicom_store_scp.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytest_plugins = ['tests._isolated_tenant']


class TestDICOMStoreSCP:
    def test_init_defaults(self):
        from services.dicom_store_scp import DICOMStoreSCP

        svc = DICOMStoreSCP()
        assert svc.ae_title == 'MEDICAL_STORE'
        assert svc.port == 11113
        assert svc._running is False
        assert svc._thread is None

    def test_init_custom(self):
        from services.dicom_store_scp import DICOMStoreSCP

        svc = DICOMStoreSCP(ae_title='MY_AE', port=11114)
        assert svc.ae_title == 'MY_AE'
        assert svc.port == 11114

    def test_start_no_pynetdicom(self, app, db, test_tenant, monkeypatch):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        from services.dicom_store_scp import DICOMStoreSCP

        svc = DICOMStoreSCP()
        # Simulate pynetdicom not being installed
        import builtins

        original_import = builtins.__import__

        def fake_import(name, *a, **k):
            if name == 'pynetdicom':
                raise ImportError('No module named pynetdicom')
            return original_import(name, *a, **k)

        monkeypatch.setattr(builtins, '__import__', fake_import)
        svc.start()  # Should return early without error
        assert svc._running is False

    def test_is_running(self):
        from services.dicom_store_scp import DICOMStoreSCP

        svc = DICOMStoreSCP()
        assert svc.is_running() is False

    def test_handle_store_success(self, app, db, test_tenant, monkeypatch):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        from services.dicom_store_scp import DICOMStoreSCP

        svc = DICOMStoreSCP()

        # Mock event with dataset
        mock_ds = MagicMock()
        mock_ds.SOPInstanceUID = '1.2.3.4'
        mock_file_meta = MagicMock()
        mock_event = MagicMock()
        mock_event.dataset = mock_ds
        mock_event.file_meta = mock_file_meta

        # Mock os.makedirs and ds.save_as
        with patch('os.makedirs'), patch.object(mock_ds, 'save_as'):
            result = svc._handle_store(mock_event)
            assert result == 0x0000  # Success

    def test_handle_store_failure(self, app, db, test_tenant, monkeypatch):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        from services.dicom_store_scp import DICOMStoreSCP

        svc = DICOMStoreSCP()

        # Mock event that raises on save_as
        mock_ds = MagicMock()
        mock_ds.SOPInstanceUID = '1.2.3.4'
        mock_file_meta = MagicMock()
        mock_event = MagicMock()
        mock_event.dataset = mock_ds
        mock_event.file_meta = mock_file_meta

        with patch('os.makedirs'), patch.object(
            mock_ds, 'save_as', side_effect=Exception('save failed')
        ):
            result = svc._handle_store(mock_event)
            assert result == 0xC000  # Failure

    def test_stop_not_running(self):
        from services.dicom_store_scp import DICOMStoreSCP

        svc = DICOMStoreSCP()
        # Should not raise
        svc.stop()

    def test_singleton(self):
        from services.dicom_store_scp import dicom_store_scp

        assert dicom_store_scp is not None
        assert dicom_store_scp.ae_title == 'MEDICAL_STORE'
