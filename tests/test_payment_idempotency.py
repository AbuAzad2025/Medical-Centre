"""Tests for P3-001: Scoped payment idempotency."""

import pytest
from sqlalchemy import func, select

from app.extensions import db
from app_factory import db as _db
from models.patient import Patient
from models.payment import Payment
from models.user import User
from models.visit import Visit
from services.payment_service import PaymentService


@pytest.fixture(scope='function')
def pay_patient(app, test_tenant):
    p = Patient(
        tenant_id=test_tenant.id,
        first_name='Pay',
        last_name='Patient',
        phone='0500000040',
    )
    _db.session.add(p)
    _db.session.commit()
    return p


@pytest.fixture(scope='function')
def pay_accountant(app, test_tenant):
    u = db.session.execute(select(User).filter_by(username='pay_accountant')).scalars().first()
    if not u:
        u = User(
            username='pay_accountant',
            email='pay_acc@example.com',
            full_name='Accountant Pay',
            role='accountant',
            is_active=True,
            tenant_id=test_tenant.id,
        )
        u.set_password('test123')
        _db.session.add(u)
        _db.session.commit()
    return u


@pytest.fixture(scope='function')
def pay_visit(app, test_tenant, pay_patient, pay_accountant):
    from models.system_config import SystemConfig

    cfg = (
        db.session.execute(
            select(SystemConfig).filter_by(config_key='allow_partial_payment_global')
        )
        .scalars()
        .first()
    )
    if not cfg:
        cfg = SystemConfig(
            config_key='allow_partial_payment_global',
            config_type='boolean',
            config_value='true',
            category='general',
        )
        _db.session.add(cfg)
    cfg.set_value(True)
    _db.session.commit()

    v = Visit(
        tenant_id=test_tenant.id,
        patient_id=pay_patient.id,
        total_amount=100,
        paid_amount=0,
        payment_status='PENDING',
        status='IN_PROGRESS',
    )
    _db.session.add(v)
    _db.session.commit()
    return v


class TestPaymentServiceIdempotency:
    def test_creates_payment_with_idempotency_key(self, pay_visit, pay_accountant, test_tenant):
        ok, payment = PaymentService.create_payment(
            tenant_id=test_tenant.id,
            operation_type='payment',
            idempotency_key='key-123',
            patient_id=pay_visit.patient_id,
            visit_id=pay_visit.id,
            amount=50,
            method='CASH',
            received_by=pay_accountant.id,
        )
        assert ok is True
        _db.session.commit()
        assert payment.idempotency_key == 'key-123'
        assert payment.operation_type == 'payment'
        assert payment.tenant_id == test_tenant.id

    def test_duplicate_idempotency_key_returns_existing(
        self, pay_visit, pay_accountant, test_tenant
    ):
        ok1, p1 = PaymentService.create_payment(
            tenant_id=test_tenant.id,
            operation_type='payment',
            idempotency_key='dup-key',
            patient_id=pay_visit.patient_id,
            visit_id=pay_visit.id,
            amount=50,
            method='CASH',
            received_by=pay_accountant.id,
        )
        assert ok1 is True
        _db.session.commit()

        ok2, p2 = PaymentService.create_payment(
            tenant_id=test_tenant.id,
            operation_type='payment',
            idempotency_key='dup-key',
            patient_id=pay_visit.patient_id,
            visit_id=pay_visit.id,
            amount=999,  # different amount should be ignored
            method='CARD',
            received_by=pay_accountant.id,
        )
        assert ok2 is True
        assert p1.id == p2.id
        assert float(p2.amount) == 50  # original value preserved

    def test_null_idempotency_key_allows_duplicates(self, pay_visit, pay_accountant, test_tenant):
        for _ in range(2):
            ok, payment = PaymentService.create_payment(
                tenant_id=test_tenant.id,
                operation_type='payment',
                idempotency_key=None,
                patient_id=pay_visit.patient_id,
                visit_id=pay_visit.id,
                amount=10,
                method='CASH',
                received_by=pay_accountant.id,
            )
            assert ok is True
            _db.session.commit()
        count = db.session.execute(
            select(func.count()).select_from(Payment).filter_by(visit_id=pay_visit.id)
        ).scalar()
        assert count == 2


class TestPaymentRouteIdempotency:
    def test_process_payment_is_idempotent(
        self, app, client, pay_visit, pay_accountant, test_tenant
    ):
        from app.core.rate_limiter import _shared_store

        _shared_store.clear()
        client.post(
            '/auth/login',
            data={
                'username': 'pay_accountant',
                'password': 'test123',
                'tenant_slug': test_tenant.slug,
            },
        )
        data = {
            'paid_amount': '50',
            'payment_method': 'cash',
            'payment_currency': 'ILS',
        }
        resp1 = client.post(f'/payment/process/{pay_visit.id}', data=data)
        assert resp1.status_code in (200, 302)

        resp2 = client.post(f'/payment/process/{pay_visit.id}', data=data)
        assert resp2.status_code in (200, 302)

        payments = (
            db.session.execute(select(Payment).filter_by(visit_id=pay_visit.id)).scalars().all()
        )
        assert len(payments) == 1
        assert float(payments[0].amount) == 50


class TestPaymentConcurrentIdempotency:
    """Simulate concurrent payment creation with identical idempotency keys."""

    def test_concurrent_idempotency_returns_single_payment_mocked(self, app):
        """When lock is held, service fetches the existing payment without creating a duplicate."""
        from decimal import Decimal
        from unittest.mock import MagicMock, patch

        from app.core.rate_limiter import IdempotencyLock

        lock = IdempotencyLock(timeout_seconds=5)
        lock_key = '1:payment:concurrent-idem-key-001'

        # Pre-acquire the lock to simulate another thread holding it
        assert lock.acquire(lock_key) is True

        try:
            # Mock an existing payment that the blocked thread should find
            mock_payment = MagicMock()
            mock_payment.id = 999
            mock_payment.amount = Decimal('50')
            mock_payment.idempotency_key = 'concurrent-idem-key-001'

            mock_execute_result = MagicMock()
            mock_execute_result.scalars.return_value.first.return_value = mock_payment

            with patch(
                'services.payment_service.db.session.execute', return_value=mock_execute_result
            ):
                with patch('services.payment_service.db.session.flush'):
                    ok, result = PaymentService.create_payment(
                        tenant_id=1,
                        operation_type='payment',
                        idempotency_key='concurrent-idem-key-001',
                        amount=50,
                    )
                    assert ok is True
                    assert result.id == 999  # returned existing, did not create new
        finally:
            lock.release(lock_key)

    def test_distinct_idempotency_keys_create_multiple_payments(
        self, app, pay_visit, pay_accountant, test_tenant
    ):
        """Distinct idempotency keys should each create a separate payment."""
        payment_ids = set()
        for i in range(5):
            ok, result = PaymentService.create_payment(
                tenant_id=test_tenant.id,
                operation_type='payment',
                idempotency_key=f'distinct-key-{i}',
                patient_id=pay_visit.patient_id,
                visit_id=pay_visit.id,
                amount=10,
                method='CASH',
                received_by=pay_accountant.id,
            )
            assert ok is True
            payment_ids.add(result.id)
            db.session.flush()

        assert len(payment_ids) == 5

    def test_idempotency_lock_prevents_race_condition(
        self, app, pay_visit, pay_accountant, test_tenant
    ):
        """Directly test that the IdempotencyLock serializes access."""
        from app.core.rate_limiter import IdempotencyLock

        lock = IdempotencyLock(timeout_seconds=5)
        key = 'test-lock-key-001'

        assert lock.acquire(key) is True
        assert lock.acquire(key) is False  # already held
        lock.release(key)
        assert lock.acquire(key) is True  # released, can re-acquire
        lock.release(key)
