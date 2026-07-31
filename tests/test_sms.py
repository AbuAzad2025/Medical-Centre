import pytest
from unittest.mock import patch, MagicMock
from app.extensions import db


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
        from unittest.mock import MagicMock, patch

        mock_nq = MagicMock()
        mock_nq.notification_type = 'sms'
        mock_nq.recipient = '+970599123456'
        mock_nq.content = 'Test SMS from queue'
        mock_nq.subject = None
        mock_nq.user_id = 1
        mock_nq.status = 'pending'
        mock_nq.id = 1
        mock_nq.tenant_id = None

        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value.all.return_value = [mock_nq]

        with patch('services.notification_service.db') as mock_db:
            mock_db.session.execute.return_value = mock_execute_result
            with patch('services.sms_service.SMSService.send_sms') as mock_send:
                mock_send.return_value = {'success': True, 'message': 'OK'}
                from services.notification_service import NotificationService
                result = NotificationService.process_notification_queue()
                assert result.get('success') is True
                mock_send.assert_called_once_with(phone='+970599123456', message='Test SMS from queue', tenant=None)


# ═════════════════════════════ OTP Rate Limiting ═════════════════════════════

class TestSMSServiceOTP:
    def test_send_otp_success(self, app):
        from services.sms_service import SMSService
        with patch.object(SMSService, 'send_sms') as mock_send:
            mock_send.return_value = {'success': True, 'message': 'Sent'}
            result = SMSService.send_otp(phone='+970599123456')
            assert result['success'] is True
            assert result['expires_in'] == 300
            assert 'otp_code' in result
            assert len(result['otp_code']) == 6
            mock_send.assert_called_once()

    def test_send_otp_empty_phone(self, app):
        from services.sms_service import SMSService
        result = SMSService.send_otp(phone='')
        assert result['success'] is False
        assert result['rate_limited'] is False

    def test_send_otp_rate_limit_3_per_5_minutes(self, app):
        from services.sms_service import SMSService
        phone = '+970599111111'

        with patch.object(SMSService, 'send_sms') as mock_send:
            mock_send.return_value = {'success': True, 'message': 'Sent'}
            # 3 requests should succeed
            for _ in range(3):
                result = SMSService.send_otp(phone=phone)
                assert result['success'] is True

            # 4th request should be rate limited
            result = SMSService.send_otp(phone=phone)
            assert result['success'] is False
            assert result['rate_limited'] is True
            assert result['retry_after'] == 300
            assert 'try again' in result['message'].lower()

    def test_send_otp_rate_limit_resets_after_window(self, app):
        from services.sms_service import SMSService
        from app.core.rate_limiter import RateLimiter
        phone = '+970599222222'

        with patch.object(SMSService, 'send_sms') as mock_send:
            mock_send.return_value = {'success': True, 'message': 'Sent'}
            # Exhaust limit
            for _ in range(3):
                SMSService.send_otp(phone=phone)
            assert SMSService.send_otp(phone=phone)['rate_limited'] is True

            # Clear the rate limiter for this namespace
            RateLimiter(max_requests=3, window_seconds=300, namespace='otp_request', use_redis=False).clear()

            result = SMSService.send_otp(phone=phone)
            assert result['success'] is True

    def test_send_otp_exponential_backoff_after_failures(self, app):
        from services.sms_service import SMSService
        phone = '+970599333333'

        with patch.object(SMSService, 'send_sms') as mock_send:
            mock_send.return_value = {'success': True, 'message': 'Sent'}
            # Send OTP successfully
            SMSService.send_otp(phone=phone)

        # Simulate 3 failed verification attempts
        for _ in range(3):
            SMSService.verify_otp(phone=phone, code='000000')

        # Next send_otp should be blocked by exponential backoff
        result = SMSService.send_otp(phone=phone)
        assert result['success'] is False
        assert result['rate_limited'] is True
        assert 'locked' in result['message'].lower() or 'failed attempts' in result['message'].lower()
        assert result['retry_after'] >= 59

    def test_send_otp_exponential_backoff_doubles(self, app):
        from services.sms_service import SMSService
        phone = '+970599444444'

        with patch.object(SMSService, 'send_sms') as mock_send:
            mock_send.return_value = {'success': True, 'message': 'Sent'}
            SMSService.send_otp(phone=phone)

        # 3 failures → 1 min lockout
        for _ in range(3):
            SMSService.verify_otp(phone=phone, code='000000')

        result = SMSService.send_otp(phone=phone)
        assert result['rate_limited'] is True
        assert 58 <= result['retry_after'] <= 60  # 2^0 * 60, allow 2s timing tolerance

        # Simulate time passing (hack: clear lockout and add more failures)
        SMSService._clear_otp_failure_data(phone)
        from app.core.rate_limiter import RateLimiter
        RateLimiter(max_requests=3, window_seconds=300, namespace='otp_request', use_redis=False).clear()
        # 4 failures → 2 min lockout
        for _ in range(4):
            SMSService.verify_otp(phone=phone, code='000000')
        result = SMSService.send_otp(phone=phone)
        assert result['rate_limited'] is True
        assert 118 <= result['retry_after'] <= 120  # 2^1 * 60

        # 5 failures → 4 min lockout
        SMSService._clear_otp_failure_data(phone)
        RateLimiter(max_requests=3, window_seconds=300, namespace='otp_request', use_redis=False).clear()
        for _ in range(5):
            SMSService.verify_otp(phone=phone, code='000000')
        result = SMSService.send_otp(phone=phone)
        assert result['rate_limited'] is True
        assert 238 <= result['retry_after'] <= 240  # 2^2 * 60

    def test_verify_otp_success_clears_failure_data(self, app):
        from services.sms_service import SMSService
        phone = '+970599555555'

        with patch.object(SMSService, 'send_sms') as mock_send:
            mock_send.return_value = {'success': True, 'message': 'Sent'}
            result = SMSService.send_otp(phone=phone)
            otp_code = result['otp_code']

        # Fail twice
        SMSService.verify_otp(phone=phone, code='000000')
        SMSService.verify_otp(phone=phone, code='000000')

        # Succeed
        assert SMSService.verify_otp(phone=phone, code=otp_code) is True

        # Failure data should be cleared, so send_otp is not blocked
        result = SMSService.send_otp(phone=phone)
        assert result['success'] is True

    def test_send_otp_backoff_capped_at_60_minutes(self, app):
        from services.sms_service import SMSService
        phone = '+970599666666'

        with patch.object(SMSService, 'send_sms') as mock_send:
            mock_send.return_value = {'success': True, 'message': 'Sent'}
            SMSService.send_otp(phone=phone)

        # 10 failures should cap at 60 min (3600 sec)
        for _ in range(10):
            SMSService.verify_otp(phone=phone, code='000000')

        result = SMSService.send_otp(phone=phone)
        assert result['rate_limited'] is True
        assert 3598 <= result['retry_after'] <= 3600  # capped, allow 2s timing tolerance

    def test_verify_otp_failure_increments_counter(self, app):
        from services.sms_service import SMSService
        phone = '+970599777777'

        with patch.object(SMSService, 'send_sms') as mock_send:
            mock_send.return_value = {'success': True, 'message': 'Sent'}
            SMSService.send_otp(phone=phone)

        assert SMSService.verify_otp(phone=phone, code='wrong') is False
        assert SMSService.verify_otp(phone=phone, code='wrong') is False
        data = SMSService._get_otp_failure_data(phone)
        assert data is not None
        assert data['count'] == 2

    def test_concurrent_otp_requests_rate_limited(self, app):
        """Simulate concurrent OTP requests from the same phone – only 3 allowed."""
        from services.sms_service import SMSService
        import threading
        phone = '+970599888888'
        results = []

        def request_otp():
            with patch.object(SMSService, 'send_sms') as mock_send:
                mock_send.return_value = {'success': True, 'message': 'Sent'}
                results.append(SMSService.send_otp(phone=phone))

        threads = [threading.Thread(target=request_otp) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        success_count = sum(1 for r in results if r['success'])
        rate_limited_count = sum(1 for r in results if r.get('rate_limited'))
        assert success_count == 3
        assert rate_limited_count == 2
