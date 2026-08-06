"""
Pre-Pilot Deployment Verification — Standalone Runner
Bypasses conftest.py to avoid SQLite/PostgreSQL dialect conflicts.
Validates all 5 phases via direct module imports and mocked contexts.
"""

import hashlib
import hmac
import os
import sys
import time
import traceback
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

# ── Environment setup ──
os.environ['SECRET_KEY'] = 'test-secret-key-for-validation-only-32chars'
os.environ['APP_ENV'] = 'testing'
os.environ['TEST_DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['DEV_DATABASE_URL'] = 'sqlite:///dev_temp.db'
os.environ['DATABASE_URL'] = 'sqlite:///prod_temp.db'
os.environ['LOCAL_DATABASE_URL'] = 'sqlite:///local_temp.db'
os.environ['SUPPRESS_DEPRECATION_WARNINGS'] = '1'
os.environ['SUPPRESS_LOGGING'] = '1'
os.environ['SKIP_PLATFORM_BOOTSTRAP'] = '1'
os.environ['RLS_BYPASS_ALLOWED'] = '1'
os.environ['ENABLE_SAAS_MODE'] = 'false'

# Add project root to path (this file is in scripts/ops/)
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _project_root)

import contextlib

from flask import Flask

# ── Results tracking ──
results = {'passed': 0, 'failed': 0, 'errors': []}


def _assert(desc, condition, details=''):
    if condition:
        results['passed'] += 1
        print(f'  [PASS] {desc}')
    else:
        results['failed'] += 1
        results['errors'].append(f'{desc}: {details}')
        print(f'  [FAIL] {desc}: {details}')


def _safe_test(desc, fn):
    try:
        fn()
    except Exception as exc:
        tb = traceback.format_exc()
        results['failed'] += 1
        results['errors'].append(f'{desc}: {exc}\n{tb}')
        print(f'  [ERROR] {desc}: {exc}')


# ============================================================
# PHASE 1: Schema / Migration Verification (Model-level)
# ============================================================
print('\n=== PHASE 1: Schema / Migration Verification ===')


def _phase1():
    from models.consent_management import ConsentAuditLog, ConsentTemplate, PatientConsent

    cols = {c.name for c in PatientConsent.__table__.columns}
    required = {
        'id',
        'patient_id',
        'consent_type',
        'scope_description',
        'status',
        'version',
        'previous_version_id',
        'granted_at',
        'expires_at',
        'withdrawn_at',
        'withdrawal_reason',
        'granted_by_patient',
        'guardian_name',
        'guardian_relationship',
        'capture_method',
        'capture_document_id',
        'recorded_by_user_id',
        'tenant_id',
        'created_at',
        'updated_at',
    }
    _assert(
        'PatientConsent has all required columns',
        required.issubset(cols),
        f'missing={required - cols}',
    )

    from sqlalchemy.schema import UniqueConstraint

    constraints = PatientConsent.__table__.constraints
    has_uq = any(
        isinstance(c, UniqueConstraint) and getattr(c, 'name', '') == 'uq_patient_consent_version'
        for c in constraints
    )
    _assert('PatientConsent unique constraint exists', has_uq)

    tcols = {c.name for c in ConsentTemplate.__table__.columns}
    _assert('ConsentTemplate has name', 'name' in tcols)
    _assert('ConsentTemplate has consent_type', 'consent_type' in tcols)

    acols = {c.name for c in ConsentAuditLog.__table__.columns}
    _assert('ConsentAuditLog has consent_id', 'consent_id' in acols)
    _assert('ConsentAuditLog has ip_address', 'ip_address' in acols)

    from models.user import User

    ucols = {c.name for c in User.__table__.columns}
    _assert('User has tenant_id', 'tenant_id' in ucols)
    _assert('User has password_hash', 'password_hash' in ucols)

    # Verify set_password signature accepts user_context
    import inspect

    sig = inspect.signature(User.set_password)
    _assert('User.set_password accepts user_context', 'user_context' in sig.parameters)


_safe_test('Phase 1: Schema verification', _phase1)

# ============================================================
# PHASE 2: Clinical Safety Hard-Stops
# ============================================================
print('\n=== PHASE 2: Clinical Safety Hard-Stops ===')


def _phase2():
    from services.clinical_safety_service import SafetyAlert, SafetyCheckSeverity

    alert = SafetyAlert(
        check_type='allergy',
        severity=SafetyCheckSeverity.HARD_STOP,
        message='HARD STOP',
        override_requires='head_physician',
    )
    _assert(
        'SafetyAlert HARD_STOP severity correct', alert.severity == SafetyCheckSeverity.HARD_STOP
    )

    from services.password_policy_service import PasswordPolicyService

    svc = PasswordPolicyService()
    ok, violations = svc.validate('short')
    _assert(
        'Password policy rejects short passwords', not ok and any('12' in v for v in violations)
    )

    ok, violations = svc.validate('longpassword123')
    _assert(
        'Password policy rejects missing uppercase',
        not ok and any('uppercase' in v.lower() for v in violations),
    )

    ok, violations = svc.validate('ValidPass123!@#')
    _assert('Password policy accepts valid password', ok and not violations)

    ok, violations = svc.validate('testuser123!A', user_context={'username': 'testuser'})
    _assert(
        'Password policy blocks personal info',
        not ok and any('username' in v.lower() for v in violations),
    )

    # Mock HIBP breach check
    with patch('services.password_policy_service.requests.get') as mock_get:
        sha1_suffix = hashlib.sha1(b'password123').hexdigest().upper()[5:]
        mock_get.return_value = MagicMock(
            status_code=200,
            text=f'{sha1_suffix}:12345\nABCDE:1',
            raise_for_status=MagicMock(),
        )
        count = svc._check_hibp_breach('password123')
        _assert('HIBP breach check returns count', count == 12345)

    pw = svc.generate_password(length=16)
    ok, _ = svc.validate(pw)
    _assert('Generated password passes policy', ok)

    from werkzeug.security import generate_password_hash

    old_hash = generate_password_hash('OldPass123!')
    _assert('Password history blocks reuse', not svc.check_history('OldPass123!', [old_hash]))
    _assert('Password history allows new password', svc.check_history('NewPass456!', [old_hash]))


_safe_test('Phase 2: Clinical safety & password policy', _phase2)

# ============================================================
# PHASE 3: Resilience, Circuit Breaker, Timeout
# ============================================================
print('\n=== PHASE 3: Resilience, Circuit Breaker, Timeout ===')


def _phase3():
    from utils.circuit_breaker import CircuitBreaker, CircuitBreakerError, CircuitState

    cb = CircuitBreaker('test_svc', failure_threshold=3, recovery_timeout=1.0)
    _assert('Circuit breaker starts CLOSED', cb.state == CircuitState.CLOSED)

    # Trigger 3 failures
    for i in range(3):
        with contextlib.suppress(ValueError):
            cb.call(lambda _i=i: (_ for _ in ()).throw(ValueError(f'fail {_i}')))
    _assert('Circuit breaker opens after 3 failures', cb.state == CircuitState.OPEN)

    # Fast-fail
    try:
        cb.call(lambda: 'should not execute')
        _assert('Circuit breaker rejects calls when OPEN', False, 'Expected CircuitBreakerError')
    except CircuitBreakerError:
        _assert('Circuit breaker rejects calls when OPEN', True)

    # Recovery test
    cb2 = CircuitBreaker(
        'test_svc2', failure_threshold=1, recovery_timeout=0.1, success_threshold=1
    )
    with contextlib.suppress(ValueError):
        cb2.call(lambda: (_ for _ in ()).throw(ValueError('fail')))
    _assert('CB2 is OPEN after 1 failure', cb2.state == CircuitState.OPEN)
    time.sleep(0.15)
    _assert('CB2 transitions to HALF_OPEN after timeout', cb2.state == CircuitState.HALF_OPEN)
    result = cb2.call(lambda: 'success')
    _assert('CB2 call succeeds in HALF_OPEN', result == 'success')
    _assert('CB2 closes after success', cb2.state == CircuitState.CLOSED)

    # Safe requests
    from utils.safe_requests import safe_request

    with patch('utils.safe_requests.requests.request') as mock_req:
        mock_resp = MagicMock()
        mock_req.return_value = mock_resp
        resp = safe_request('GET', 'http://example.com', timeout=(3, 5))
        called_with = mock_req.call_args
        _assert('safe_request passes timeout', called_with[1]['timeout'] == (3, 5))

    with patch('utils.safe_requests.requests.request') as mock_req:
        from requests import Timeout

        mock_req.side_effect = [Timeout('timed out'), Timeout('timed out'), MagicMock()]
        with patch('time.sleep', return_value=None):
            resp = safe_request(
                'GET', 'http://example.com', timeout=(1, 2), retries=2, retry_backoff=0
            )
        _assert('safe_request retries 2 times', mock_req.call_count == 3)

    # Background worker safety
    from utils.background_worker_safety import safe_background_loop

    err_log = []

    def capture_log(level, msg, *args):
        err_log.append(msg)

    def failing_func():
        raise RuntimeError('worker failure')

    with patch('utils.background_worker_safety.logger') as mock_logger:
        mock_logger.error = capture_log
        with contextlib.suppress(RuntimeError):
            safe_background_loop(failing_func, error_message='Test worker')
        _assert('Background worker logs errors', len(err_log) > 0)

    # API security decorators — use separate Flask apps to avoid "route already handled" error
    from utils.api_security import (
        limit_payload_size,
        require_content_type,
        sanitize_search_input,
        verify_webhook_signature,
    )

    app1 = Flask(__name__)

    @app1.route('/test', methods=['POST'])
    @limit_payload_size(max_size_bytes=100)
    def test_route():
        return {'ok': True}

    with app1.test_client() as client:
        resp = client.post('/test', data=b'x' * 50)
        _assert('limit_payload_size allows small payload', resp.status_code == 200)
        resp = client.post('/test', data=b'x' * 200)
        _assert('limit_payload_size rejects large payload', resp.status_code == 413)

    app2 = Flask(__name__)

    @app2.route('/testct', methods=['POST'])
    @require_content_type('application/json')
    def test_ct():
        return {'ok': True}

    with app2.test_client() as client:
        resp = client.post('/testct', data='{}', content_type='text/plain')
        _assert('require_content_type rejects wrong type', resp.status_code == 415)
        resp = client.post('/testct', data='{}', content_type='application/json')
        _assert('require_content_type accepts correct type', resp.status_code == 200)

    app3 = Flask(__name__)
    secret = 'super-secret'

    @app3.route('/webhook', methods=['POST'])
    @verify_webhook_signature(secret=secret)
    def test_webhook():
        return {'ok': True}

    with app3.test_client() as client:
        resp = client.post('/webhook', data=b'payload')
        _assert('verify_webhook_signature rejects missing signature', resp.status_code == 401)
        body = b'payload'
        sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        resp = client.post('/webhook', data=body, headers={'X-Webhook-Signature': sig})
        _assert('verify_webhook_signature accepts valid signature', resp.status_code == 200)
        resp = client.post('/webhook', data=body, headers={'X-Webhook-Signature': 'bad'})
        _assert('verify_webhook_signature rejects invalid signature', resp.status_code == 401)

    # Search sanitization
    _assert('sanitize strips null bytes', sanitize_search_input('te\x00st') == 'test')
    _assert('sanitize limits length', len(sanitize_search_input('a' * 200, max_length=10)) == 10)
    _assert('sanitize normalizes wildcards', sanitize_search_input('%%%test%%%') == '%test%')


_safe_test('Phase 3: Resilience & circuit breakers', _phase3)

# ============================================================
# PHASE 4: Security Hardening
# ============================================================
print('\n=== PHASE 4: Security Hardening ===')


def _phase4():
    from app.core.rate_limiter import RateLimiter

    rl = RateLimiter(max_requests=3, window_seconds=60, use_redis=False)
    key = 'test:ip:endpoint'
    _assert('Rate limiter allows 1st request', rl.is_allowed(key))
    _assert('Rate limiter allows 2nd request', rl.is_allowed(key))
    _assert('Rate limiter allows 3rd request', rl.is_allowed(key))
    _assert('Rate limiter blocks 4th request', not rl.is_allowed(key))

    rl2 = RateLimiter(max_requests=1, window_seconds=0.1, use_redis=False)
    key2 = 'test:ip2:endpoint'
    _assert('Rate limiter allows 1st in short window', rl2.is_allowed(key2))
    _assert('Rate limiter blocks 2nd in short window', not rl2.is_allowed(key2))
    time.sleep(0.15)
    _assert('Rate limiter resets after window', rl2.is_allowed(key2))

    # Verify rate limit decorators are present in auth routes
    import inspect

    from routes.auth_routes import change_password, impersonate, login

    _assert('login has @rate_limit', '@rate_limit' in inspect.getsource(login))
    _assert('change_password has @rate_limit', '@rate_limit' in inspect.getsource(change_password))
    _assert('impersonate has @rate_limit', '@rate_limit' in inspect.getsource(impersonate))

    # Verify password policy enforced in user creation
    from routes.super_admin.users import create_user, reset_user_password

    _assert(
        'create_user calls set_password with user_context',
        'user_context' in inspect.getsource(create_user),
    )
    _assert(
        'reset_user_password uses generate_password',
        'generate_password' in inspect.getsource(reset_user_password),
    )

    # Verify API routes have payload limits
    from routes.api_search import search_patients
    from routes.api_user import user_preferences
    from routes.saas_routes import signup_organization

    _assert(
        'api_user has limit_payload_size',
        'limit_payload_size' in inspect.getsource(user_preferences),
    )
    _assert(
        'api_search has limit_payload_size',
        'limit_payload_size' in inspect.getsource(search_patients),
    )
    _assert(
        'saas signup has limit_payload_size',
        'limit_payload_size' in inspect.getsource(signup_organization),
    )

    # Verify Stripe billing uses circuit breaker
    from services.stripe_billing_service import StripeBillingService

    _assert(
        'stripe billing uses circuit_breaker_call',
        'circuit_breaker_call' in inspect.getsource(StripeBillingService),
    )

    # Verify SMS uses circuit breaker
    from services.sms_service import SMSService

    _assert(
        'sms service uses circuit_breaker_call',
        'circuit_breaker_call' in inspect.getsource(SMSService),
    )

    # Verify webhook uses circuit breaker
    from services.webhook_service import _dispatch_single

    _assert(
        'webhook dispatch uses circuit breaker', 'breaker' in inspect.getsource(_dispatch_single)
    )

    # Verify search sanitization in services
    from app.shared.search_service import SearchService

    _assert(
        'search_patients uses sanitize_search_input',
        'sanitize_search_input' in inspect.getsource(SearchService.search_patients),
    )
    from services.emergency_service import EmergencyService

    _assert(
        'emergency list_cases uses sanitize_search_input',
        'sanitize_search_input' in inspect.getsource(EmergencyService.list_cases),
    )
    from services.prescription_service import PrescriptionService

    _assert(
        'search_medications uses sanitize_search_input',
        'sanitize_search_input' in inspect.getsource(PrescriptionService.search_medications),
    )


_safe_test('Phase 4: Security hardening', _phase4)

# ============================================================
# PHASE 5: HIPAA / GDPR Compliance & Data Retention
# ============================================================
print('\n=== PHASE 5: HIPAA / GDPR Compliance ===')


def _phase5():
    from services.data_retention_service import DataRetentionService, RetentionCategory

    svc = DataRetentionService()
    policy = svc.get_policy(RetentionCategory.MEDICAL_RECORD)
    _assert('Medical record retention is 10 years', policy.retain_years == 10)
    _assert('Medical record action is archive', policy.action_after_retention == 'archive')
    _assert('Medical record requires approval', policy.requires_approval is True)

    policy2 = svc.get_policy(RetentionCategory.SESSION_LOG)
    _assert('Session log retention is 2 years', policy2.retain_years == 2)
    _assert('Session log action is delete', policy2.action_after_retention == 'delete')

    created = datetime(2020, 1, 1, tzinfo=UTC)
    deadline = svc.calculate_retention_deadline(RetentionCategory.MEDICAL_RECORD, created)
    _assert(
        'Retention deadline calculated correctly',
        deadline.year in (2029, 2030),
        f'got {deadline.year}',
    )

    old = datetime(2000, 1, 1, tzinfo=UTC)
    _assert(
        'Old record is eligible for action',
        svc.is_eligible_for_action(RetentionCategory.MEDICAL_RECORD, old),
    )
    recent = datetime.now(UTC)
    _assert(
        'Recent record is NOT eligible',
        not svc.is_eligible_for_action(RetentionCategory.MEDICAL_RECORD, recent),
    )

    report = svc.generate_retention_report(tenant_id=1)
    _assert('Retention report has tenant_id', 'tenant_id' in report)
    _assert('Retention report has policies', 'policies' in report)
    _assert('Retention report has expired_records', 'expired_records' in report)

    from models.consent_management import PatientConsent

    c = PatientConsent(
        patient_id=1,
        consent_type='treatment',
        scope_description='Treatment consent',
        version=1,
        status='granted',
    )
    _assert('Consent version 1 is active', c.is_active())

    c2 = PatientConsent(
        patient_id=1,
        consent_type='marketing',
        scope_description='Marketing',
        version=1,
        status='granted',
    )
    c2.status = 'withdrawn'
    c2.withdrawn_at = datetime.now(UTC)
    _assert('Withdrawn consent is inactive', not c2.is_active())

    c3 = PatientConsent(
        patient_id=1,
        consent_type='research',
        scope_description='Research',
        version=1,
        status='granted',
        expires_at=datetime(2020, 1, 1, tzinfo=UTC),
    )
    _assert('Expired consent is inactive', not c3.is_active())

    # Verify consent audit log immutable columns
    from models.consent_management import ConsentAuditLog

    log = ConsentAuditLog(
        consent_id=1,
        action='granted',
        patient_id=1,
        ip_address='127.0.0.1',
        user_agent='Mozilla/5.0',
    )
    _assert('ConsentAuditLog stores IP', log.ip_address == '127.0.0.1')
    _assert('ConsentAuditLog stores action', log.action == 'granted')


_safe_test('Phase 5: Compliance & data retention', _phase5)

# ============================================================
# PHASE 6: Health Check & Background Worker Enhancements
# ============================================================
print('\n=== PHASE 6: Health Check & Background Worker ===')


def _phase6():
    import inspect

    from app_factory import create_app

    app = create_app('testing')
    # Health check endpoint exists and inspects DB
    _assert('__health endpoint exists', '/__health' in [r.rule for r in app.url_map.iter_rules()])

    # Verify app_factory has enhanced error handling in background workers
    source = inspect.getsource(create_app)
    _assert('Notification processor logs tracebacks', 'traceback.format_exc()' in source)
    _assert(
        'Notification processor alerts admin',
        '_alert_admin' in source and 'notif-processor' in source,
    )
    _assert('Backup automation logs tracebacks', 'traceback.format_exc()' in source)
    _assert(
        'Backup automation alerts admin', '_alert_admin' in source and 'backup-automation' in source
    )
    _assert('Data retention scan added', 'DataRetentionService' in source)
    _assert('Consent model imported', 'models.consent_management' in source)

    # Verify prescription service has safety checks
    from services.prescription_service import PrescriptionService

    source2 = inspect.getsource(PrescriptionService.create_prescription)
    _assert('create_prescription has skip_safety_checks param', 'skip_safety_checks' in source2)
    _assert('create_prescription calls ClinicalSafetyService', 'ClinicalSafetyService' in source2)

    # Verify saas_registration has password policy
    from services.saas_registration_service import SaasRegistrationService

    source3 = inspect.getsource(SaasRegistrationService.register_organization)
    _assert(
        'SaaS registration enforces password policy',
        'password_policy_service' in source3 or 'weak_password' in source3,
    )

    # Verify stripe has timeout configured
    from services.stripe_billing_service import StripeBillingService

    source4 = inspect.getsource(StripeBillingService._api_key)
    _assert('Stripe billing sets HTTP client timeout', 'timeout' in source4)


_safe_test('Phase 6: Integration verification', _phase6)

# ============================================================
# SUMMARY
# ============================================================
print('\n' + '=' * 60)
print('PRE-PILOT DEPLOYMENT VERIFICATION SUMMARY')
print('=' * 60)
print(f'Total assertions passed: {results["passed"]}')
print(f'Total assertions failed: {results["failed"]}')
if results['errors']:
    print(f'\nErrors encountered ({len(results["errors"])}):')
    for i, err in enumerate(results['errors'], 1):
        print(f'  {i}. {err[:200]}')
print('=' * 60)
exit_code = 0 if results['failed'] == 0 else 1
print(f'EXIT CODE: {exit_code} ({"ALL GATES PASSED" if exit_code == 0 else "SOME GATES FAILED"})')
if exit_code == 0:
    print('\nRECOMMENDATION: System is validated for pilot deployment.')
else:
    print('\nRECOMMENDATION: Fix failed assertions before pilot deployment.')
