"""Tests for services.payment_service.PaymentService and
services.refund_service.RefundService.

Focus: idempotency, FK validity, Decimal accuracy, exact-case financial enums,
and the full refund lifecycle (request -> approve/reject -> execute) including
invoice reversal and receipt voiding. All DB work runs under ``rollback_db``.
"""
import types
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from services.payment_service import PaymentService as PS
from services.refund_service import RefundService as RS
from models.payment import Payment, PaymentStatus
from models.refund_request import RefundRequest, RefundStatus
from models.receipt import Receipt
from models.invoice import Invoice
from models.patient import Patient
from models.visit import Visit
from models.user import User


@pytest.fixture
def fx(rollback_db):
    db = rollback_db

    def user():
        un = 'pr_' + uuid.uuid4().hex[:8]
        u = User(username=un, email=un + '@x.com', full_name='u', role='accountant', is_active=True)
        u.set_password('p')
        db.session.add(u)
        db.session.commit()
        return u

    def patient():
        p = Patient(first_name='د', last_name='ف')
        db.session.add(p)
        db.session.commit()
        return p

    def visit(patient_id=None):
        v = Visit(patient_id=patient_id or patient().id)
        db.session.add(v)
        db.session.commit()
        return v

    def invoice(visit_id, total=100, paid=0, status='ISSUED'):
        inv = Invoice(invoice_number='INV-' + uuid.uuid4().hex[:8], visit_id=visit_id,
                      created_by=user().id, status=status, currency='ILS',
                      total_amount=total, paid_amount=paid)
        db.session.add(inv)
        db.session.commit()
        return inv

    def payment(amount=100, status='CONFIRMED', visit_id=None, tenant_id=None):
        pay = Payment(tenant_id=tenant_id, operation_type='visit_payment',
                      amount=Decimal(str(amount)), currency='ILS', status=status,
                      method='CASH', visit_id=visit_id,
                      payment_date=datetime.now(timezone.utc))
        db.session.add(pay)
        db.session.commit()
        return pay

    def receipt(payment_obj, visit_obj):
        r = Receipt(receipt_number='RC-' + uuid.uuid4().hex[:8], visit_id=visit_obj.id,
                    patient_id=visit_obj.patient_id, payment_id=payment_obj.id,
                    total_amount=100, paid_amount=100, payment_method='cash',
                    status='issued', created_by=user().id)
        db.session.add(r)
        db.session.commit()
        return r

    return types.SimpleNamespace(db=db, user=user, patient=patient, visit=visit,
                                 invoice=invoice, payment=payment, receipt=receipt)


# ════════════════════════════ PaymentService ════════════════════════════

class TestCreatePayment:
    def test_requires_operation_type(self, fx):
        ok, msg = PS.create_payment(tenant_id=None, operation_type='',
                                    idempotency_key=None, amount=10)
        assert ok is False and 'operation_type' in msg

    def test_basic_create(self, fx):
        ok, pay = PS.create_payment(tenant_id=None, operation_type='visit_payment',
                                    idempotency_key=None, amount='25.50', currency='ILS')
        assert ok is True
        assert pay.amount == Decimal('25.50')
        assert pay.currency == 'ILS'
        assert pay.status == 'CONFIRMED'

    def test_decimal_accuracy_from_float(self, fx):
        ok, pay = PS.create_payment(tenant_id=None, operation_type='op',
                                    idempotency_key=None, amount=19.99)
        assert ok is True
        assert pay.amount == Decimal('19.99')

    def test_idempotency_returns_existing(self, fx):
        key = 'idem-' + uuid.uuid4().hex[:8]
        ok1, p1 = PS.create_payment(tenant_id=None, operation_type='visit_payment',
                                    idempotency_key=key, amount=10)
        fx.db.session.flush()
        ok2, p2 = PS.create_payment(tenant_id=None, operation_type='visit_payment',
                                    idempotency_key=key, amount=10)
        assert ok1 and ok2
        assert p1.id == p2.id

    def test_idempotency_distinct_keys_create_two(self, fx):
        ok1, p1 = PS.create_payment(tenant_id=None, operation_type='op',
                                    idempotency_key='k1-' + uuid.uuid4().hex[:6], amount=10)
        ok2, p2 = PS.create_payment(tenant_id=None, operation_type='op',
                                    idempotency_key='k2-' + uuid.uuid4().hex[:6], amount=10)
        assert p1.id != p2.id

    def test_invalid_amount_returns_error(self, fx):
        ok, msg = PS.create_payment(tenant_id=None, operation_type='op',
                                    idempotency_key=None, amount='not-a-number')
        assert ok is False
        assert isinstance(msg, str)

    def test_confirmed_payment_allocates_to_invoice(self, fx):
        v = fx.visit()
        inv = fx.invoice(v.id, total=100, paid=0)
        ok, pay = PS.create_payment(tenant_id=None, operation_type='visit_payment',
                                    idempotency_key=None, amount=60, visit_id=v.id,
                                    status='CONFIRMED')
        assert ok is True
        fx.db.session.flush()
        assert Decimal(str(Invoice.query.get(inv.id).paid_amount or 0)) > 0


# ════════════════════════════ RefundService ════════════════════════════

class TestRequestRefund:
    def test_payment_not_found(self, fx):
        ok, msg = RS.request_refund(tenant_id=None, payment_id=99999999, amount=10, reason='r')
        assert ok is False and 'not found' in msg

    def test_tenant_mismatch(self, fx):
        pay = fx.payment(tenant_id=None)
        ok, msg = RS.request_refund(tenant_id=999, payment_id=pay.id, amount=10, reason='r')
        assert ok is False and 'mismatch' in msg.lower()

    def test_non_refundable_status(self, fx):
        pay = fx.payment(amount=100, status='PENDING')
        ok, msg = RS.request_refund(tenant_id=None, payment_id=pay.id, amount=10, reason='r')
        assert ok is False and 'refundable' in msg.lower()

    def test_amount_must_be_positive(self, fx):
        pay = fx.payment(amount=100, status='CONFIRMED')
        ok, msg = RS.request_refund(tenant_id=None, payment_id=pay.id, amount=0, reason='r')
        assert ok is False and 'positive' in msg.lower()

    def test_amount_exceeds_payment(self, fx):
        pay = fx.payment(amount=50, status='CONFIRMED')
        ok, msg = RS.request_refund(tenant_id=None, payment_id=pay.id, amount=100, reason='r')
        assert ok is False and 'exceeds' in msg.lower()

    def test_success(self, fx):
        pay = fx.payment(amount=100, status='CONFIRMED')
        ok, req = RS.request_refund(tenant_id=None, payment_id=pay.id, amount=40, reason='dup charge')
        assert ok is True
        assert req.status == RefundStatus.PENDING
        assert req.amount == Decimal('40')

    def test_duplicate_pending_rejected(self, fx):
        pay = fx.payment(amount=100, status='CONFIRMED')
        RS.request_refund(tenant_id=None, payment_id=pay.id, amount=10, reason='r')
        fx.db.session.flush()
        ok, msg = RS.request_refund(tenant_id=None, payment_id=pay.id, amount=10, reason='r2')
        assert ok is False and 'pending refund' in msg.lower()


class TestApproveReject:
    def _pending(self, fx):
        pay = fx.payment(amount=100, status='CONFIRMED')
        ok, req = RS.request_refund(tenant_id=None, payment_id=pay.id, amount=30, reason='r')
        fx.db.session.flush()
        return req

    def test_approve_success(self, fx):
        req = self._pending(fx)
        u = fx.user()
        ok, r = RS.approve_refund(req.id, approved_by=u.id)
        assert ok is True
        assert r.status == RefundStatus.APPROVED
        assert r.approved_by == u.id and r.approved_at is not None

    def test_approve_not_found(self, fx):
        ok, msg = RS.approve_refund(99999999, approved_by=1)
        assert ok is False and 'not found' in msg

    def test_approve_non_pending(self, fx):
        req = self._pending(fx)
        u = fx.user()
        RS.approve_refund(req.id, approved_by=u.id)
        fx.db.session.flush()
        ok, msg = RS.approve_refund(req.id, approved_by=u.id)
        assert ok is False and 'not pending' in msg.lower()

    def test_reject_success(self, fx):
        req = self._pending(fx)
        u = fx.user()
        ok, r = RS.reject_refund(req.id, rejected_by=u.id, reason='invalid')
        assert ok is True
        assert r.status == RefundStatus.REJECTED
        assert r.notes == 'invalid'

    def test_reject_not_found(self, fx):
        ok, msg = RS.reject_refund(99999999, rejected_by=1)
        assert ok is False


class TestExecuteRefund:
    def test_not_found(self, fx):
        ok, msg = RS.execute_refund(99999999, executed_by=1)
        assert ok is False and 'not found' in msg

    def test_not_approved(self, fx):
        pay = fx.payment(amount=100, status='CONFIRMED')
        ok, req = RS.request_refund(tenant_id=None, payment_id=pay.id, amount=10, reason='r')
        fx.db.session.flush()
        ok2, msg = RS.execute_refund(req.id, executed_by=1)
        assert ok2 is False and 'not approved' in msg.lower()

    def test_full_lifecycle_reverses_invoice_and_voids_receipt(self, fx):
        u = fx.user()
        v = fx.visit()
        inv = fx.invoice(v.id, total=100, paid=100, status='PAID')
        pay = fx.payment(amount=100, status='CONFIRMED', visit_id=v.id)
        rec = fx.receipt(pay, v)
        ok, req = RS.request_refund(tenant_id=None, payment_id=pay.id, amount=100, reason='full refund')
        fx.db.session.flush()
        RS.approve_refund(req.id, approved_by=u.id)
        fx.db.session.flush()
        ok3, r = RS.execute_refund(req.id, executed_by=u.id)
        assert ok3 is True
        assert r.status == RefundStatus.EXECUTED
        assert Payment.query.get(pay.id).status == PaymentStatus.REFUNDED
        assert Decimal(str(Invoice.query.get(inv.id).paid_amount or 0)) == Decimal('0')
        assert Receipt.query.get(rec.id).status == 'voided'
