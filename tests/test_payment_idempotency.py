"""Tests for P3-001: Scoped payment idempotency."""

import pytest

from app_factory import db as _db
from models.invoice import Invoice
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
    u = User.query.filter_by(username='pay_accountant').first()
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
    cfg = SystemConfig.query.filter_by(config_key='allow_partial_payment_global').first()
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

    def test_duplicate_idempotency_key_returns_existing(self, pay_visit, pay_accountant, test_tenant):
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
        count = Payment.query.filter_by(visit_id=pay_visit.id).count()
        assert count == 2


class TestPaymentRouteIdempotency:
    def test_process_payment_is_idempotent(self, app, client, pay_visit, pay_accountant, test_tenant):
        from app.core.rate_limiter import _shared_store
        _shared_store.clear()
        client.post('/auth/login', data={
            'username': 'pay_accountant',
            'password': 'test123',
            'tenant_slug': test_tenant.slug,
        })
        data = {
            'paid_amount': '50',
            'payment_method': 'cash',
            'payment_currency': 'ILS',
        }
        resp1 = client.post(f'/payment/process/{pay_visit.id}', data=data)
        assert resp1.status_code in (200, 302)

        resp2 = client.post(f'/payment/process/{pay_visit.id}', data=data)
        assert resp2.status_code in (200, 302)

        payments = Payment.query.filter_by(visit_id=pay_visit.id).all()
        assert len(payments) == 1
        assert float(payments[0].amount) == 50
