"""Tests for P3-006: Refund/Reversal vertical slice."""

import pytest

from app_factory import db as _db
from models.invoice import Invoice, InvoiceService
from models.patient import Patient
from models.payment import Payment, PaymentStatus
from models.receipt import Receipt
from models.refund_request import RefundRequest, RefundStatus
from models.user import User
from models.visit import Visit
from services.refund_service import RefundService


@pytest.fixture(scope='function')
def refund_patient(app, test_tenant):
    p = Patient(
        tenant_id=test_tenant.id,
        first_name='Refund',
        last_name='Patient',
        phone='0500000080',
    )
    _db.session.add(p)
    _db.session.commit()
    return p


@pytest.fixture(scope='function')
def refund_accountant(app, test_tenant):
    u = User.query.filter_by(username='refund_accountant').first()
    if not u:
        u = User(
            username='refund_accountant',
            email='refund_acc@example.com',
            full_name='Accountant Refund',
            role='accountant',
            is_active=True,
            tenant_id=test_tenant.id,
        )
        u.set_password('test123')
        _db.session.add(u)
        _db.session.commit()
    return u


@pytest.fixture(scope='function')
def refund_manager(app, test_tenant):
    u = User.query.filter_by(username='refund_manager').first()
    if not u:
        u = User(
            username='refund_manager',
            email='refund_mgr@example.com',
            full_name='Manager Refund',
            role='manager',
            is_active=True,
            tenant_id=test_tenant.id,
        )
        u.set_password('test123')
        _db.session.add(u)
        _db.session.commit()
    return u


@pytest.fixture(scope='function')
def refund_visit(app, test_tenant, refund_patient):
    v = Visit(
        tenant_id=test_tenant.id,
        patient_id=refund_patient.id,
        status='IN_PROGRESS',
    )
    _db.session.add(v)
    _db.session.commit()
    return v


@pytest.fixture(scope='function')
def refund_invoice(app, test_tenant, refund_visit):
    inv = Invoice(
        tenant_id=test_tenant.id,
        visit_id=refund_visit.id,
        total_amount=100,
        paid_amount=0,
        status='ISSUED',
    )
    _db.session.add(inv)
    _db.session.flush()
    line = InvoiceService(
        tenant_id=test_tenant.id,
        invoice_id=inv.id,
        visit_id=refund_visit.id,
        service_code='SRV',
        service_name='Service',
        quantity=1,
        unit_price=100,
        total_price=100,
    )
    _db.session.add(line)
    _db.session.commit()
    return inv


@pytest.fixture(scope='function')
def refund_payment(app, test_tenant, refund_visit, refund_patient, refund_accountant, refund_invoice):
    p = Payment(
        tenant_id=test_tenant.id,
        visit_id=refund_visit.id,
        patient_id=refund_patient.id,
        amount=100,
        method='CASH',
        status='CONFIRMED',
        received_by=refund_accountant.id,
    )
    _db.session.add(p)
    _db.session.commit()
    # Simulate allocation having happened.
    refund_invoice.paid_amount = 100
    refund_invoice.status = 'PAID'
    _db.session.commit()
    return p


class TestRefundService:
    def test_request_refund_creates_pending_request(self, test_tenant, refund_payment, refund_accountant):
        ok, req = RefundService.request_refund(
            tenant_id=test_tenant.id,
            payment_id=refund_payment.id,
            amount=50,
            reason='Overpayment',
            requested_by=refund_accountant.id,
        )
        assert ok is True
        assert req.status == RefundStatus.PENDING
        assert float(req.amount) == 50
        _db.session.commit()

    def test_request_refund_rejects_amount_exceeding_payment(self, test_tenant, refund_payment, refund_accountant):
        ok, msg = RefundService.request_refund(
            tenant_id=test_tenant.id,
            payment_id=refund_payment.id,
            amount=200,
            reason='Too much',
            requested_by=refund_accountant.id,
        )
        assert ok is False
        assert 'exceeds' in msg.lower()

    def test_request_refund_rejects_non_confirmed_payment(self, test_tenant, refund_payment, refund_accountant):
        refund_payment.status = PaymentStatus.PENDING
        _db.session.commit()
        ok, msg = RefundService.request_refund(
            tenant_id=test_tenant.id,
            payment_id=refund_payment.id,
            amount=50,
            reason='Test',
            requested_by=refund_accountant.id,
        )
        assert ok is False
        assert 'refundable' in msg.lower()

    def test_approve_refund(self, test_tenant, refund_payment, refund_accountant, refund_manager):
        ok, req = RefundService.request_refund(
            tenant_id=test_tenant.id,
            payment_id=refund_payment.id,
            amount=50,
            reason='Overpayment',
            requested_by=refund_accountant.id,
        )
        _db.session.commit()
        ok, req = RefundService.approve_refund(req.id, approved_by=refund_manager.id)
        assert ok is True
        assert req.status == RefundStatus.APPROVED
        assert req.approved_by == refund_manager.id

    def test_execute_refund_reverses_allocation_and_voids_receipt(self, test_tenant, refund_payment, refund_accountant, refund_manager, refund_invoice):
        # Create a receipt for the payment.
        from services.billing_state_service import ReceiptService
        ReceiptService.issue_receipt(refund_payment.visit, refund_payment)

        ok, req = RefundService.request_refund(
            tenant_id=test_tenant.id,
            payment_id=refund_payment.id,
            amount=30,
            reason='Partial refund',
            requested_by=refund_accountant.id,
        )
        _db.session.commit()
        ok, req = RefundService.approve_refund(req.id, approved_by=refund_manager.id)
        assert ok is True

        ok, req = RefundService.execute_refund(req.id, executed_by=refund_manager.id)
        assert ok is True
        _db.session.commit()

        _db.session.refresh(refund_payment)
        _db.session.refresh(refund_invoice)
        assert refund_payment.status == PaymentStatus.REFUNDED
        assert req.status == RefundStatus.EXECUTED
        assert float(refund_invoice.paid_amount) == 70
        assert refund_invoice.status == 'PARTIAL'

        receipt = _db.session.query(Receipt).filter_by(payment_id=refund_payment.id).first()
        assert receipt.status == 'voided'
