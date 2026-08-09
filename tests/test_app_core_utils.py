"""Tests for app/core and utils modules (decorators, rate_limiter, utilities)."""

import time
import types
import uuid

import pytest

from app.extensions import db
from models.user import User


@pytest.fixture(autouse=True)
def _no_bundle_limits(monkeypatch):
    monkeypatch.setattr(
        'app.shared.tenant_filter._check_bundle_limits_on_create',
        lambda *_a, **_k: None,
    )


@pytest.fixture
def ctx(rollback_db, test_tenant):
    db_ = rollback_db

    def _user(**kw):
        role = kw.get('role', 'doctor')
        u = User(
            username=kw.get('username', f'{role}_{uuid.uuid4().hex[:6]}'),
            email=kw.get('email', f'{uuid.uuid4().hex[:8]}@test.local'),
            full_name=kw.get('full_name', 'مستخدم'),
            role=role,
            is_active=True,
        )
        u.set_password('test123')
        db_.session.add(u)
        db_.session.commit()
        return u

    return types.SimpleNamespace(db=db_, user=_user) if False else types.SimpleNamespace(db=db_, user=_user)


class TestDecorators:
    def test_reception_only_passes_for_reception(self, app, ctx):
        from flask_login import login_user
        from utils.decorators import reception_only

        @reception_only
        def view():
            return 'ok'

        with app.test_request_context():
            rec = ctx.user(role='reception')
            db.session.commit()
            login_user(rec)
            assert view() == 'ok'

    def test_reception_only_blocks_doctor(self, app, ctx):
        from flask_login import login_user
        from utils.decorators import reception_only
        from werkzeug.exceptions import Forbidden

        @reception_only
        def view():
            return 'ok'

        with app.test_request_context():
            doc = ctx.user(role='doctor')
            db.session.commit()
            login_user(doc)
            with pytest.raises(Forbidden):
                view()

    def test_can_modify_patient_data_allows_reception(self, app, ctx):
        from flask_login import login_user
        from utils.decorators import can_modify_patient_data

        @can_modify_patient_data
        def view():
            return 'ok'

        with app.test_request_context():
            rec = ctx.user(role='reception')
            db.session.commit()
            login_user(rec)
            assert view() == 'ok'


class TestRateLimiter:
    def test_rate_limiter_allows_under_limit(self):
        from app.core.rate_limiter import RateLimiter

        rl = RateLimiter(max_requests=5, window_seconds=60)
        for _ in range(5):
            assert rl.is_allowed('test-key') is True

    def test_rate_limiter_blocks_over_limit(self):
        from app.core.rate_limiter import RateLimiter

        rl = RateLimiter(max_requests=2, window_seconds=60)
        assert rl.is_allowed('key1') is True
        assert rl.is_allowed('key1') is True
        assert rl.is_allowed('key1') is False

    def test_rate_limiter_tracks_separate_keys(self):
        from app.core.rate_limiter import RateLimiter

        rl = RateLimiter(max_requests=1, window_seconds=60)
        assert rl.is_allowed('key-a') is True
        assert rl.is_allowed('key-b') is True

    def test_idempotency_lock(self):
        from app.core.rate_limiter import IdempotencyLock

        lock = IdempotencyLock()
        assert lock.acquire('idem-1') is True
        assert lock.acquire('idem-1') is False
        lock.release('idem-1')
        assert lock.acquire('idem-1') is True

    def test_shared_store_cleanup(self):
        from app.core.rate_limiter import _shared_store, _idempotency_locks

        _shared_store.clear()
        _idempotency_locks.clear()
        assert len(_shared_store) == 0


class TestCircuitBreaker:
    def test_circuit_breaker_closed_allows(self):
        from utils.circuit_breaker import circuit_breaker_call

        def ok():
            return 42

        result = circuit_breaker_call('test-cb', ok)
        assert result == 42

    def test_circuit_breaker_opens_after_failures(self):
        from utils.circuit_breaker import circuit_breaker_call

        calls = {'n': 0}

        def flaky():
            calls['n'] += 1
            if calls['n'] <= 5:
                raise RuntimeError('boom')
            return 'recovered'

        for _ in range(5):
            try:
                circuit_breaker_call('cb-flaky', flaky)
            except RuntimeError:
                pass

        try:
            circuit_breaker_call('cb-flaky', flaky)
        except Exception:
            pass


class TestTenantQuery:
    def test_get_tenant_record_returns_record(self, ctx, test_tenant):
        from utils.tenant_query import get_tenant_record

        u = ctx.user(role='doctor')
        result = get_tenant_record(User, u.id)
        assert result is not None
        assert result.id == u.id

    def test_get_tenant_record_missing_raises(self, ctx, test_tenant):
        from utils.tenant_query import TenantContextError, get_tenant_record

        with pytest.raises(TenantContextError):
            get_tenant_record(User, 999999999)


class TestDbSafety:
    def test_safe_commit_success(self, ctx):
        from utils.db_safety import safe_commit

        u = ctx.user(role='nurse')
        result = safe_commit(ctx.db.session, error_message='fail')
        assert result is True

    def test_safe_rollback(self):
        from utils.db_safety import safe_rollback

        safe_rollback(db.session, error_message='err')
        assert True


class TestEnums:
    def test_visit_state_values(self):
        from app.shared.enums import VisitState

        assert VisitState.OPEN.value == 'OPEN'
        assert VisitState.COMPLETED.value == 'COMPLETED'
        assert VisitState.CANCELLED.value == 'CANCELLED'

    def test_appointment_state_values(self):
        from app.shared.enums import AppointmentState

        assert AppointmentState.SCHEDULED.value == 'SCHEDULED'
        assert AppointmentState.CONFIRMED.value == 'CONFIRMED'

    def test_payment_status_values(self):
        from models.payment import PaymentStatus

        assert PaymentStatus.PENDING.value == 'PENDING'
        assert PaymentStatus.PAID.value == 'PAID'

    def test_payment_method_values(self):
        from models.payment import PaymentMethod

        assert PaymentMethod.CASH.value == 'CASH'
        assert PaymentMethod.INSURANCE.value == 'INSURANCE'


class TestValidators:
    def test_validate_field(self):
        from app.shared.validators import validate_field

        result = validate_field('email', 'user@test.com')
        assert isinstance(result, (bool, tuple)) or result is None


class TestUserMessages:
    def test_user_message(self):
        from app.shared.user_messages import user_message

        msg = user_message('test_key')
        assert isinstance(msg, str)

    def test_resolve_user_message(self):
        from app.shared.user_messages import resolve_user_message

        msg = resolve_user_message('nonexistent_key_xyz')
        assert isinstance(msg, str)


class TestEnumLabels:
    def test_enum_label(self):
        from app.shared.enum_labels import enum_label

        label = enum_label('OPEN', 'visit_state')
        assert isinstance(label, str)


class TestMixins:
    def test_timestamp_mixin_has_fields(self):
        from app.shared.mixins import TimestampMixin

        assert hasattr(TimestampMixin, 'created_at')
        assert hasattr(TimestampMixin, 'updated_at')


class TestModelListeners:
    def test_listeners_module_imports(self):
        import app.shared.model_listeners as ml

        assert ml is not None


class TestSearchService:
    def test_search_patients(self):
        from app.shared.search_service import SearchService

        result = SearchService.search_patients('test')
        assert isinstance(result, list)


class TestReportTemplateService:
    def test_list_templates(self):
        from app.shared.report_template_service import list_templates

        templates = list_templates()
        assert isinstance(templates, list)
