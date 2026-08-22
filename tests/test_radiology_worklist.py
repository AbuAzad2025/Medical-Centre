"""Tests for routes.radiology.worklist module.

Covers radiology worklist routes and helper functions.
"""

import pytest
from unittest.mock import MagicMock, patch

from routes.radiology.worklist import (
    _parse_radiology_payload,
    _handle_radiology_file_uploads,
    _notify_radiology_complete,
)


class TestParseRadiologyPayload:
    """Tests for _parse_radiology_payload function."""

    def test_parses_json_payload(self):
        """Test parsing JSON payload."""
        with patch('routes.radiology.worklist.request') as mock_request:
            mock_request.is_json = True
            mock_request.get_json = MagicMock(
                return_value={'is_critical': True, 'findings': 'test'}
            )
            payload, is_critical = _parse_radiology_payload()
            assert payload == {'is_critical': True, 'findings': 'test'}
            assert is_critical is True

    def test_parses_form_payload(self):
        """Test parsing form payload."""
        with patch('routes.radiology.worklist.request') as mock_request:
            mock_request.is_json = False
            mock_request.form = {'is_critical': 'on', 'findings': 'test'}
            payload, is_critical = _parse_radiology_payload()
            assert 'findings' in payload
            assert is_critical is True

    def test_parses_form_payload_empty(self):
        """Test parsing empty form payload."""
        with patch('routes.radiology.worklist.request') as mock_request:
            mock_request.is_json = False
            mock_request.form = {}
            payload, is_critical = _parse_radiology_payload()
            assert payload == {}
            assert is_critical is False

    def test_is_critical_from_list(self):
        """Test is_critical from list value."""
        with patch('routes.radiology.worklist.request') as mock_request:
            mock_request.is_json = True
            mock_request.get_json = MagicMock(return_value={'is_critical': ['true']})
            payload, is_critical = _parse_radiology_payload()
            assert is_critical is True

    def test_is_critical_from_bool(self):
        """Test is_critical from boolean value."""
        with patch('routes.radiology.worklist.request') as mock_request:
            mock_request.is_json = True
            mock_request.get_json = MagicMock(return_value={'is_critical': True})
            payload, is_critical = _parse_radiology_payload()
            assert is_critical is True

    def test_is_critical_from_int(self):
        """Test is_critical from int value."""
        with patch('routes.radiology.worklist.request') as mock_request:
            mock_request.is_json = True
            mock_request.get_json = MagicMock(return_value={'is_critical': 1})
            payload, is_critical = _parse_radiology_payload()
            assert is_critical is True

    def test_is_critical_from_string_on(self):
        """Test is_critical from 'on' string."""
        with patch('routes.radiology.worklist.request') as mock_request:
            mock_request.is_json = False
            mock_request.form = {'is_critical': 'on'}
            payload, is_critical = _parse_radiology_payload()
            assert is_critical is True

    def test_is_critical_from_string_yes(self):
        """Test is_critical from 'yes' string."""
        with patch('routes.radiology.worklist.request') as mock_request:
            mock_request.is_json = False
            mock_request.form = {'is_critical': 'yes'}
            payload, is_critical = _parse_radiology_payload()
            assert is_critical is True

    def test_is_critical_from_string_1(self):
        """Test is_critical from '1' string."""
        with patch('routes.radiology.worklist.request') as mock_request:
            mock_request.is_json = False
            mock_request.form = {'is_critical': '1'}
            payload, is_critical = _parse_radiology_payload()
            assert is_critical is True

    def test_is_critical_from_string_true(self):
        """Test is_critical from 'true' string."""
        with patch('routes.radiology.worklist.request') as mock_request:
            mock_request.is_json = False
            mock_request.form = {'is_critical': 'true'}
            payload, is_critical = _parse_radiology_payload()
            assert is_critical is True

    def test_is_critical_false_string(self):
        """Test is_critical from 'false' string."""
        with patch('routes.radiology.worklist.request') as mock_request:
            mock_request.is_json = False
            mock_request.form = {'is_critical': 'false'}
            payload, is_critical = _parse_radiology_payload()
            assert is_critical is False

    def test_is_critical_empty_list(self):
        """Test is_critical from empty list."""
        with patch('routes.radiology.worklist.request') as mock_request:
            mock_request.is_json = True
            mock_request.get_json = MagicMock(return_value={'is_critical': []})
            payload, is_critical = _parse_radiology_payload()
            assert is_critical is False

    def test_is_critical_none(self):
        """Test is_critical is None."""
        with patch('routes.radiology.worklist.request') as mock_request:
            mock_request.is_json = True
            mock_request.get_json = MagicMock(return_value={})
            payload, is_critical = _parse_radiology_payload()
            assert is_critical is False

    def test_json_payload_no_is_critical(self):
        """Test JSON payload without is_critical key."""
        with patch('routes.radiology.worklist.request') as mock_request:
            mock_request.is_json = True
            mock_request.get_json = MagicMock(return_value={'findings': 'test'})
            payload, is_critical = _parse_radiology_payload()
            assert payload == {'findings': 'test'}
            assert is_critical is False


class TestHandleRadiologyFileUploads:
    """Tests for _handle_radiology_file_uploads function."""

    def test_no_files_returns_early(self):
        """Test that None files returns immediately."""
        result = _handle_radiology_file_uploads(None, MagicMock(), {})
        assert result is None

    def test_empty_files_returns_early(self):
        """Test that empty files list returns immediately."""
        result = _handle_radiology_file_uploads([], MagicMock(), {})
        assert result is None

    @patch('routes.radiology.worklist.current_user')
    @patch('routes.radiology.worklist.current_app')
    @patch('routes.radiology.worklist.os')
    @patch('routes.radiology.worklist.secrets')
    @patch('routes.radiology.worklist.secure_filename')
    @patch('routes.radiology.worklist.db')
    def test_processes_single_file(
        self,
        mock_db,
        mock_secure,
        mock_secrets,
        mock_os,
        mock_app,
        mock_user,
    ):
        """Test processing a single file upload."""
        mock_user.id = 7
        mock_app_config = {}
        mock_os.path.join = lambda *args: '/'.join(str(a) for a in args)
        mock_os.path.dirname = lambda *args: '/tmp'
        mock_os.path.abspath = lambda *args: '/tmp/test.py'
        mock_os.path.splitext = lambda x: (x, '.dcm')
        mock_os.path.getsize = lambda x: 1024
        mock_os.makedirs = MagicMock()
        mock_secrets.token_hex.return_value = 'abc123'
        mock_secure.return_value = 'test.dcm'

        mock_file = MagicMock()
        mock_file.filename = 'test.dcm'
        mock_file.mimetype = 'application/dicom'
        mock_file.save = MagicMock()

        result_obj = MagicMock()
        result_obj.id = 1
        payload = {'file_description': 'Test image'}

        _handle_radiology_file_uploads([mock_file], result_obj, payload)

    @patch('routes.radiology.worklist.os')
    def test_skips_file_without_filename(self, mock_os):
        """Test skipping file without filename."""
        mock_file = MagicMock()
        mock_file.filename = None
        result_obj = MagicMock()
        result_obj.id = 1
        _handle_radiology_file_uploads([mock_file], result_obj, {})

    @patch('routes.radiology.worklist.current_user')
    @patch('routes.radiology.worklist.current_app')
    @patch('routes.radiology.worklist.os')
    @patch('routes.radiology.worklist.secure_filename')
    @patch('routes.radiology.worklist.db')
    def test_handles_empty_filename_after_secure(
        self, mock_db, mock_secure, mock_os, mock_app, mock_user
    ):
        """Test handling when secure_filename returns empty string."""
        mock_user.id = 7
        mock_app.config = {}
        mock_os.path.join = lambda *args: '/'.join(str(a) for a in args)
        mock_os.path.dirname = lambda *args: '/tmp'
        mock_os.path.splitext = lambda x: (x, '.dcm')
        mock_os.makedirs = MagicMock()
        mock_secure.return_value = ''  # Forces fallback

        mock_file = MagicMock()
        mock_file.filename = 'test.dcm'
        mock_file.save = MagicMock()

        result_obj = MagicMock()
        result_obj.id = 1
        with patch('routes.radiology.worklist.secrets') as mock_secrets:
            mock_secrets.token_hex.return_value = 'fallback'
            _handle_radiology_file_uploads([mock_file], result_obj, {})


class TestNotifyRadiologyComplete:
    """Tests for _notify_radiology_complete function."""

    def test_notify_with_doctor_id_not_critical(self):
        """Test notification when not critical."""
        mock_req = MagicMock()
        mock_req.id = 42
        mock_req.patient_id = 10
        mock_req.requester = MagicMock()
        mock_req.requester.id = 5

        mock_service = MagicMock()
        with patch('services.notification_service.NotificationService') as mock_service_cls:
            mock_service_cls.return_value = mock_service
            _notify_radiology_complete(mock_req, False)
            mock_service_cls.send_notification.assert_called_once()

    def test_notify_with_doctor_id_critical(self):
        """Test notification when critical."""
        mock_req = MagicMock()
        mock_req.id = 42
        mock_req.patient_id = 10
        mock_req.requester = MagicMock()
        mock_req.requester.id = 5

        mock_service = MagicMock()
        with patch('services.notification_service.NotificationService') as mock_service_cls:
            mock_service_cls.return_value = mock_service
            _notify_radiology_complete(mock_req, True)
            assert mock_service_cls.send_notification.call_count == 2

    def test_notify_without_doctor(self):
        """Test notification without requester."""
        mock_req = MagicMock()
        mock_req.id = 42
        mock_req.patient_id = 10
        mock_req.requester = None

        with patch('services.notification_service.NotificationService') as mock_service_cls:
            _notify_radiology_complete(mock_req, False)
            mock_service_cls.return_value.send_notification.assert_not_called()

    def test_notify_handles_exception(self):
        """Test that notification exceptions are caught."""
        mock_req = MagicMock()
        mock_req.id = 42
        mock_req.patient_id = 10
        mock_req.requester = MagicMock()
        mock_req.requester.id = 5

        with patch('services.notification_service.NotificationService') as mock_service_cls:
            mock_service_cls.return_value.send_notification.side_effect = Exception('Network error')
            _notify_radiology_complete(mock_req, False)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
