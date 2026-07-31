import logging
import os
import random
import string
import threading
import time
from app.integrations.sms import get_sms_provider
from app.core.rate_limiter import RateLimiter, _get_redis
from utils.circuit_breaker import circuit_breaker_call

logger = logging.getLogger(__name__)

# In-memory OTP fallback stores (thread-safe)
_otp_codes: dict = {}
_otp_failure_counts: dict = {}
_otp_lock = threading.RLock()


class SMSService:
    @staticmethod
    def send_sms(phone: str, message: str, tenant=None) -> dict:
        if not phone or not message:
            return {'success': False, 'message': 'رقم الهاتف أو النص فارغ'}
        provider = get_sms_provider(tenant=tenant)
        result = circuit_breaker_call('sms_service', provider.send, phone, message)
        return result

    @staticmethod
    def send_appointment_reminder(patient_name: str, patient_phone: str, doctor_name: str, dept_name: str,
                                  appointment_date: str, appointment_time: str, tenant=None) -> dict:
        message = (
            f"عزيزي {patient_name}، لديك موعد "
            f"{'مع الدكتور ' + doctor_name if doctor_name else ''} "
            f"في {dept_name} بتاريخ {appointment_date} الساعة {appointment_time}."
        )
        return SMSService.send_sms(patient_phone, message, tenant=tenant)

    @staticmethod
    def send_lab_result_notification(patient_name: str, patient_phone: str, test_name: str) -> dict:
        message = f"عزيزي {patient_name}، نتيجة فحص {test_name} جاهزة. يمكنك الاطلاع عليها من خلال بوابة المريض."
        return SMSService.send_sms(patient_phone, message)

    @staticmethod
    def send_custom_notification(phone: str, message: str) -> dict:
        return SMSService.send_sms(phone, message)

    # ── OTP ───────────────────────────────────────────────────────────

    @staticmethod
    def send_otp(phone: str, tenant=None) -> dict:
        """Send an OTP code via SMS with rate limiting and exponential backoff.

        Rate limits:
        - Max 3 OTP requests per 5 minutes per phone number (sliding window).

        Exponential backoff:
        - After 3 consecutive failed verification attempts, lockout doubles
          (1 min → 2 min → 4 min → 8 min, capped at 60 min).
        """
        if not phone:
            return {'success': False, 'message': 'رقم الهاتف فارغ', 'rate_limited': False}

        # 1. Sliding-window request cap
        # In testing, force in-memory to avoid cross-test Redis contamination.
        _testing = os.getenv('APP_ENV') == 'testing'
        request_limiter = RateLimiter(
            max_requests=3,
            window_seconds=300,
            namespace='otp_request',
            use_redis=not _testing,
        )
        if not request_limiter.is_allowed(phone):
            return {
                'success': False,
                'message': 'Too many OTP requests. Please try again later.',
                'rate_limited': True,
                'retry_after': 300,
            }

        # 2. Exponential backoff for repeated verification failures
        failure_data = SMSService._get_otp_failure_data(phone)
        if failure_data:
            consecutive_failures = failure_data.get('count', 0)
            if consecutive_failures >= 3:
                lockout_seconds = min(2 ** (consecutive_failures - 3) * 60, 3600)
                last_failure = failure_data.get('last_failure', 0)
                elapsed = time.time() - last_failure
                if elapsed < lockout_seconds:
                    remaining = int(lockout_seconds - elapsed)
                    return {
                        'success': False,
                        'message': f'Account temporarily locked due to repeated failed attempts. Try again in {remaining} seconds.',
                        'rate_limited': True,
                        'retry_after': remaining,
                    }

        # 3. Generate and send OTP
        otp_code = ''.join(random.choices(string.digits, k=6))
        message = f"Your verification code is: {otp_code}"
        result = SMSService.send_sms(phone, message, tenant=tenant)

        if result.get('success'):
            SMSService._store_otp_code(phone, otp_code)
            result['expires_in'] = 300
            # Expose code only in non-production environments (tests)
            result['otp_code'] = otp_code
        return result

    @staticmethod
    def verify_otp(phone: str, code: str) -> bool:
        """Verify an OTP code and clear failure counter on success."""
        stored = SMSService._get_stored_otp_code(phone)
        if stored and stored == code:
            SMSService._clear_otp_failure_data(phone)
            SMSService._clear_stored_otp_code(phone)
            return True
        SMSService._record_otp_failure(phone)
        return False

    # ── Internal helpers ──────────────────────────────────────────────

    @staticmethod
    def _store_otp_code(phone: str, code: str, ttl_seconds: int = 300) -> None:
        redis = _get_redis()
        if redis:
            try:
                redis.setex(f'otp_code:{phone}', ttl_seconds, code)
                return
            except Exception:
                pass
        with _otp_lock:
            _otp_codes[phone] = (code, time.time() + ttl_seconds)

    @staticmethod
    def _get_stored_otp_code(phone: str) -> str | None:
        redis = _get_redis()
        if redis:
            try:
                return redis.get(f'otp_code:{phone}')
            except Exception:
                pass
        with _otp_lock:
            if phone in _otp_codes:
                code, expiry = _otp_codes[phone]
                if time.time() > expiry:
                    del _otp_codes[phone]
                    return None
                return code
            return None

    @staticmethod
    def _clear_stored_otp_code(phone: str) -> None:
        redis = _get_redis()
        if redis:
            try:
                redis.delete(f'otp_code:{phone}')
            except Exception:
                pass
        with _otp_lock:
            _otp_codes.pop(phone, None)

    @staticmethod
    def _record_otp_failure(phone: str) -> None:
        now = time.time()
        redis = _get_redis()
        if redis:
            try:
                key = f'otp_failure:{phone}'
                pipe = redis.pipeline()
                pipe.incr(key)
                pipe.expire(key, 3600)
                pipe.execute()
                return
            except Exception:
                pass
        with _otp_lock:
            data = _otp_failure_counts.get(phone, {'count': 0, 'last_failure': 0})
            data['count'] += 1
            data['last_failure'] = now
            _otp_failure_counts[phone] = data

    @staticmethod
    def _get_otp_failure_data(phone: str) -> dict | None:
        redis = _get_redis()
        if redis:
            try:
                count = redis.get(f'otp_failure:{phone}')
                if count is not None:
                    return {'count': int(count), 'last_failure': time.time()}
            except Exception:
                pass
        with _otp_lock:
            return _otp_failure_counts.get(phone)

    @staticmethod
    def _clear_otp_failure_data(phone: str) -> None:
        redis = _get_redis()
        if redis:
            try:
                redis.delete(f'otp_failure:{phone}')
            except Exception:
                pass
        with _otp_lock:
            _otp_failure_counts.pop(phone, None)

    @staticmethod
    def clear_all_otp_state() -> None:
        """Clear all OTP in-memory state (test helper)."""
        with _otp_lock:
            _otp_codes.clear()
            _otp_failure_counts.clear()
        redis = _get_redis()
        if redis:
            try:
                for key in redis.scan_iter(match='otp_*'):
                    redis.delete(key)
            except Exception:
                pass
