import pytest
from unittest.mock import patch, MagicMock


class TestSMSProvider:
    def test_log_provider_sends_message(self, app):
        from app.integrations.sms import get_sms_provider, LogSMSProvider
        provider = get_sms_provider()
        assert isinstance(provider, LogSMSProvider)
        with patch.object(provider, 'send', wraps=provider.send) as mock_send:
            result = provider.send('+970599123456', 'Test message')
            assert result['success'] is True
            mock_send.assert_called_once_with('+970599123456', 'Test message')


class TestSMSService:
    def test_send_sms_success(self, app):
        from services.sms_service import SMSService
        with patch('services.sms_service.get_sms_provider') as mock_factory:
            mock_provider = MagicMock()
            mock_provider.send.return_value = {'success': True, 'message': 'OK'}
            mock_factory.return_value = mock_provider
            result = SMSService.send_sms(phone='+970599123456', message='Hello')
            assert result['success'] is True
            mock_provider.send.assert_called_once_with('+970599123456', 'Hello')

    def test_send_sms_empty_phone(self, app):
        from services.sms_service import SMSService
        result = SMSService.send_sms(phone='', message='Hello')
        assert result['success'] is False

    def test_send_sms_empty_message(self, app):
        from services.sms_service import SMSService
        result = SMSService.send_sms(phone='+970599123456', message='')
        assert result['success'] is False

    def test_send_appointment_reminder(self, app):
        from services.sms_service import SMSService
        with patch.object(SMSService, 'send_sms') as mock_send:
            mock_send.return_value = {'success': True, 'message': 'OK'}
            result = SMSService.send_appointment_reminder(
                patient_name='أحمد', patient_phone='+970599123456',
                doctor_name='د. محمد', dept_name='القلبية',
                appointment_date='2026-06-22', appointment_time='10:30'
            )
            assert result['success'] is True
            mock_send.assert_called_once()
            args, kwargs = mock_send.call_args
            phone = kwargs.get('phone') or args[0]
            assert phone == '+970599123456'

    def test_send_lab_result_notification(self, app):
        from services.sms_service import SMSService
        with patch.object(SMSService, 'send_sms') as mock_send:
            mock_send.return_value = {'success': True}
            result = SMSService.send_lab_result_notification(
                patient_name='أحمد', patient_phone='+970599123456',
                test_name='CBC'
            )
            assert result['success'] is True
            mock_send.assert_called_once()


class TestNotificationQueueSMS:
    def test_sms_notification_processed(self, app):
        from unittest.mock import MagicMock

        mock_nq = MagicMock()
        mock_nq.notification_type = 'sms'
        mock_nq.recipient = '+970599123456'
        mock_nq.content = 'Test SMS from queue'
        mock_nq.subject = None
        mock_nq.user_id = 1
        mock_nq.status = 'pending'
        mock_nq.id = 1
        mock_nq.tenant_id = None

        with patch('services.notification_service.NotificationQueue') as MockNQ:
            query_mock = MagicMock()
            query_mock.filter_by.return_value.all.return_value = [mock_nq]
            MockNQ.query = query_mock
            with patch('services.sms_service.SMSService.send_sms') as mock_send:
                mock_send.return_value = {'success': True, 'message': 'OK'}
                with patch('services.notification_service.db') as mock_db:
                    mock_db.session.commit.return_value = None
                    from services.notification_service import NotificationService
                    result = NotificationService.process_notification_queue()
                    assert result.get('success') is True
                    mock_send.assert_called_once_with(phone='+970599123456', message='Test SMS from queue', tenant=None)
