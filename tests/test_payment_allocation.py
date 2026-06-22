"""Tests for P3-002: Payment allocation activation and transactional posting."""

import pytest

from app_factory import db as _db
from models.invoice import Invoice, InvoiceService
from models.patient import Patient
from models.payment import Payment
from models.user import User
from models.visit import Visit
from services.billing_state_service import PaymentAllocationService
from services.payment_service import PaymentService


@pytest.fixture(scope='function')
def alloc_patient(app, test_tenant):
    p = Patient(
        tenant_id=test_tenant.id,
        first_name='Alloc',
        last_name='Patient',
        phone='0500000050',
    )
    _db.session.add(p)
    _db.session.commit()
    return p


@pytest.fixture(scope='function')
def alloc_accountant(app, test_tenant):
    u = User.query.filter_by(username='alloc_accountant').first()
    if not u:
        u = User(
            username='alloc_accountant',
            email='alloc_acc@example.com',
            full_name='Accountant Alloc',
            role='accountant',
            is_active=True,
            tenant_id=test_tenant.id,
        )
        u.set_password('test123')
        _db.session.add(u)
        _db.session.commit()
    return u


@pytest.fixture(scope='function')
def alloc_visit(app, test_tenant, alloc_patient):
    v = Visit(
        tenant_id=test_tenant.id,
        patient_id=alloc_patient.id,
        status='IN_PROGRESS',
    )
    _db.session.add(v)
    _db.session.commit()
    return v


@pytest.fixture(scope='function')
def alloc_invoice(app, test_tenant, alloc_visit):
    inv = Invoice(
        tenant_id=test_tenant.id,
        visit_id=alloc_visit.id,
        total_amount=100,
        paid_amount=0,
        status='ISSUED',
    )
    _db.session.add(inv)
    _db.session.flush()
    line = InvoiceService(
        tenant_id=test_tenant.id,
        invoice_id=inv.id,
        visit_id=alloc_visit.id,
        service_code='SRV',
        service_name='Service',
        quantity=1,
        unit_price=100,
        total_price=100,
    )
    _db.session.add(line)
    _db.session.commit()
    return inv


class TestPaymentAllocationService:
    def test_allocates_fully_to_single_invoice(self, alloc_visit, alloc_invoice, alloc_accountant, test_tenant):
        payment = Payment(
            tenant_id=test_tenant.id,
            visit_id=alloc_visit.id,
            patient_id=alloc_visit.patient_id,
            amount=100,
            method='CASH',
            status='CONFIRMED',
            received_by=alloc_accountant.id,
        )
        _db.session.add(payment)
        _db.session.flush()

        PaymentAllocationService.allocate(payment, alloc_visit)
        _db.session.commit()

        _db.session.refresh(alloc_invoice)
        assert float(alloc_invoice.paid_amount) == 100

    def test_allocates_partially_across_invoices(self, alloc_visit, alloc_invoice, alloc_accountant, test_tenant):
        inv2 = Invoice(
            tenant_id=test_tenant.id,
            visit_id=alloc_visit.id,
            total_amount=50,
            paid_amount=0,
            status='ISSUED',
        )
        _db.session.add(inv2)
        _db.session.commit()

        payment = Payment(
            tenant_id=test_tenant.id,
            visit_id=alloc_visit.id,
            patient_id=alloc_visit.patient_id,
            amount=120,
            method='CASH',
            status='CONFIRMED',
            received_by=alloc_accountant.id,
        )
        _db.session.add(payment)
        _db.session.flush()

        PaymentAllocationService.allocate(payment, alloc_visit)
        _db.session.commit()

        _db.session.refresh(alloc_invoice)
        _db.session.refresh(inv2)
        assert float(alloc_invoice.paid_amount) == 100
        assert float(inv2.paid_amount) == 20


class TestPaymentServiceAllocation:
    def test_creates_payment_and_allocates(self, alloc_visit, alloc_invoice, alloc_accountant, test_tenant):
        ok, payment = PaymentService.create_payment(
            tenant_id=test_tenant.id,
            operation_type='payment',
            idempotency_key=None,
            patient_id=alloc_visit.patient_id,
            visit_id=alloc_visit.id,
            amount=80,
            method='CASH',
            status='CONFIRMED',
            received_by=alloc_accountant.id,
        )
        assert ok is True
        _db.session.commit()

        _db.session.refresh(alloc_invoice)
        assert float(alloc_invoice.paid_amount) == 80

    def test_pending_payment_is_not_allocated(self, alloc_visit, alloc_invoice, alloc_accountant, test_tenant):
        ok, payment = PaymentService.create_payment(
            tenant_id=test_tenant.id,
            operation_type='payment',
            idempotency_key=None,
            patient_id=alloc_visit.patient_id,
            visit_id=alloc_visit.id,
            amount=80,
            method='CASH',
            status='PENDING',
            received_by=alloc_accountant.id,
        )
        assert ok is True
        _db.session.commit()

        _db.session.refresh(alloc_invoice)
        assert float(alloc_invoice.paid_amount) == 0
