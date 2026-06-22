"""Tests for P3-003: Invoice paid/balance projection and reconciliation."""

import pytest

from app_factory import db as _db
from models.invoice import Invoice, InvoiceService
from models.patient import Patient
from models.payment import Payment
from models.user import User
from models.visit import Visit
from services.financial_service import FinancialService


@pytest.fixture(scope='function')
def recon_patient(app, test_tenant):
    p = Patient(
        tenant_id=test_tenant.id,
        first_name='Recon',
        last_name='Patient',
        phone='0500000060',
    )
    _db.session.add(p)
    _db.session.commit()
    return p


@pytest.fixture(scope='function')
def recon_accountant(app, test_tenant):
    u = User.query.filter_by(username='recon_accountant').first()
    if not u:
        u = User(
            username='recon_accountant',
            email='recon_acc@example.com',
            full_name='Accountant Recon',
            role='accountant',
            is_active=True,
            tenant_id=test_tenant.id,
        )
        u.set_password('test123')
        _db.session.add(u)
        _db.session.commit()
    return u


@pytest.fixture(scope='function')
def recon_visit(app, test_tenant, recon_patient):
    v = Visit(
        tenant_id=test_tenant.id,
        patient_id=recon_patient.id,
        status='IN_PROGRESS',
    )
    _db.session.add(v)
    _db.session.commit()
    return v


@pytest.fixture(scope='function')
def recon_invoice(app, test_tenant, recon_visit):
    inv = Invoice(
        tenant_id=test_tenant.id,
        visit_id=recon_visit.id,
        total_amount=100,
        paid_amount=0,
        status='ISSUED',
    )
    _db.session.add(inv)
    _db.session.flush()
    line = InvoiceService(
        tenant_id=test_tenant.id,
        invoice_id=inv.id,
        visit_id=recon_visit.id,
        service_code='SRV',
        service_name='Service',
        quantity=1,
        unit_price=100,
        total_price=100,
    )
    _db.session.add(line)
    _db.session.commit()
    return inv


class TestInvoiceBalanceDue:
    def test_balance_due_property(self, recon_invoice):
        assert recon_invoice.balance_due == 100.0
        recon_invoice.paid_amount = 30
        assert recon_invoice.balance_due == 70.0

    def test_balance_due_never_negative(self, recon_invoice):
        recon_invoice.paid_amount = 150
        assert recon_invoice.balance_due == 0.0

    def test_to_dict_includes_balance_due(self, recon_invoice):
        data = recon_invoice.to_dict()
        assert 'balance_due' in data
        assert data['balance_due'] == 100.0


class TestFinancialServiceReconcileVisitPayments:
    def test_reconcile_allocates_payment(self, recon_visit, recon_invoice, recon_accountant, test_tenant):
        payment = Payment(
            tenant_id=test_tenant.id,
            visit_id=recon_visit.id,
            patient_id=recon_visit.patient_id,
            amount=60,
            method='CASH',
            status='CONFIRMED',
            received_by=recon_accountant.id,
        )
        _db.session.add(payment)
        _db.session.commit()

        result = FinancialService.reconcile_visit_payments(recon_visit.id)
        assert result['ok'] is True
        _db.session.commit()

        _db.session.refresh(recon_invoice)
        assert float(recon_invoice.paid_amount) == 60
        assert recon_invoice.status == 'PARTIAL'
        assert recon_invoice.balance_due == 40

    def test_reconcile_resets_and_reallocates(self, recon_visit, recon_invoice, recon_accountant, test_tenant):
        # Simulate an out-of-sync paid_amount
        recon_invoice.paid_amount = 999
        _db.session.commit()

        payment = Payment(
            tenant_id=test_tenant.id,
            visit_id=recon_visit.id,
            patient_id=recon_visit.patient_id,
            amount=100,
            method='CASH',
            status='CONFIRMED',
            received_by=recon_accountant.id,
        )
        _db.session.add(payment)
        _db.session.commit()

        result = FinancialService.reconcile_visit_payments(recon_visit.id)
        assert result['ok'] is True
        _db.session.commit()

        _db.session.refresh(recon_invoice)
        assert float(recon_invoice.paid_amount) == 100
        assert recon_invoice.status == 'PAID'
        assert recon_invoice.balance_due == 0

    def test_reconcile_multiple_invoices_fifo(self, recon_visit, recon_invoice, recon_accountant, test_tenant):
        inv2 = Invoice(
            tenant_id=test_tenant.id,
            visit_id=recon_visit.id,
            total_amount=50,
            paid_amount=0,
            status='ISSUED',
        )
        _db.session.add(inv2)
        _db.session.commit()

        payment = Payment(
            tenant_id=test_tenant.id,
            visit_id=recon_visit.id,
            patient_id=recon_visit.patient_id,
            amount=120,
            method='CASH',
            status='CONFIRMED',
            received_by=recon_accountant.id,
        )
        _db.session.add(payment)
        _db.session.commit()

        result = FinancialService.reconcile_visit_payments(recon_visit.id)
        assert result['ok'] is True
        _db.session.commit()

        _db.session.refresh(recon_invoice)
        _db.session.refresh(inv2)
        assert float(recon_invoice.paid_amount) == 100
        assert recon_invoice.status == 'PAID'
        assert float(inv2.paid_amount) == 20
        assert inv2.status == 'PARTIAL'

    def test_reconcile_ignores_non_confirmed_payments(self, recon_visit, recon_invoice, recon_accountant, test_tenant):
        payment = Payment(
            tenant_id=test_tenant.id,
            visit_id=recon_visit.id,
            patient_id=recon_visit.patient_id,
            amount=100,
            method='CASH',
            status='PENDING',
            received_by=recon_accountant.id,
        )
        _db.session.add(payment)
        _db.session.commit()

        result = FinancialService.reconcile_visit_payments(recon_visit.id)
        assert result['ok'] is True
        _db.session.commit()

        _db.session.refresh(recon_invoice)
        assert float(recon_invoice.paid_amount) == 0
        assert recon_invoice.status == 'ISSUED'
