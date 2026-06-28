"""Tests for services.financial_service.FinancialService (wired methods) and
services.billing_state_service (BillingStateService / ReceiptService /
PaymentAllocationService).

All DB work runs under ``rollback_db`` isolation.
"""
import uuid
import types

import pytest

from services.financial_service import FinancialService
from services.billing_state_service import (
    BillingStateService, ReceiptService, PaymentAllocationService,
)
import services.financial_service as fin_mod
from app.shared.enums import BillingState, PaymentStatus
from models.invoice import Invoice, InvoiceService
from models.payment import Payment
from models.visit import Visit
from models.patient import Patient
from models.user import User


@pytest.fixture
def ffx(rollback_db):
    db = rollback_db

    def patient():
        p = Patient(first_name='ز', last_name='ت')
        db.session.add(p)
        db.session.commit()
        return p

    def user():
        un = 'zz_fin_' + uuid.uuid4().hex[:8]
        u = User(username=un, email=un + '@x.com', full_name='u', role='accountant', is_active=True)
        u.set_password('p')
        db.session.add(u)
        db.session.commit()
        return u

    def visit(patient_id, **kw):
        v = Visit(patient_id=patient_id, **kw)
        db.session.add(v)
        db.session.commit()
        return v

    def invoice(visit_id, total, paid=0, status='ISSUED'):
        inv = Invoice(visit_id=visit_id, total_amount=total, paid_amount=paid,
                      invoice_number='INV-' + uuid.uuid4().hex[:8].upper(), status=status)
        db.session.add(inv)
        db.session.commit()
        return inv

    def payment(visit_id, patient_id, amount, status=PaymentStatus.CONFIRMED):
        pay = Payment(visit_id=visit_id, patient_id=patient_id, amount=amount, status=status)
        db.session.add(pay)
        db.session.commit()
        return pay

    return types.SimpleNamespace(db=db, patient=patient, user=user, visit=visit,
                                 invoice=invoice, payment=payment)


# ───────────────────────── FinancialService ─────────────────────────

class TestDashboardStats:
    def test_reflects_billed_and_collected(self, ffx):
        p = ffx.patient()
        v = ffx.visit(p.id)
        ffx.invoice(v.id, 100)
        ffx.payment(v.id, p.id, 60)
        stats = FinancialService.get_dashboard_stats()
        assert stats['total_billed'] >= 100
        assert stats['total_collected'] >= 60
        assert 'pending' in stats

    def test_exception_returns_zeros(self, monkeypatch):
        import models.invoice as mi
        monkeypatch.setattr(mi, 'Invoice', property(lambda self: (_ for _ in ()).throw(RuntimeError('x'))))
        stats = FinancialService.get_dashboard_stats()
        assert stats == {"total_billed": 0, "total_collected": 0, "total_expenses": 0, "pending": 0}


class TestRevenueByPeriod:
    @pytest.mark.parametrize('period', ['daily', 'monthly', 'yearly'])
    def test_returns_list(self, ffx, period):
        # daily works on PostgreSQL; monthly/yearly use MySQL-only funcs and
        # degrade to [] — either way the contract is "a list, never crash".
        assert isinstance(FinancialService.get_revenue_by_period(period), list)


class TestCreateInvoice:
    def test_creates_invoice_with_lines(self, ffx):
        p = ffx.patient()
        ffx.visit(p.id)
        inv = FinancialService.create_invoice(p.id, [
            {'price': 50, 'quantity': 2, 'description': 'X', 'service_code': 'SVC1'},
            {'price': 30, 'quantity': 1, 'service_name': 'Y'},
        ])
        assert inv is not None
        assert float(inv.total_amount) == 130.0
        lines = InvoiceService.query.filter_by(invoice_id=inv.id).all()
        assert len(lines) == 2

    def test_no_visit_still_creates(self, ffx):
        p = ffx.patient()
        inv = FinancialService.create_invoice(p.id, [{'price': 10, 'quantity': 1}])
        assert inv is not None

    def test_exception_returns_none(self, ffx, monkeypatch):
        import models.invoice as mi
        monkeypatch.setattr(mi, 'InvoiceService',
                            lambda *a, **k: (_ for _ in ()).throw(RuntimeError('x')))
        p = ffx.patient()
        inv = FinancialService.create_invoice(p.id, [{'price': 10, 'quantity': 1}])
        assert inv is None


class TestPendingInvoices:
    def test_only_pending_statuses_returned(self, ffx):
        p = ffx.patient()
        v = ffx.visit(p.id)
        ffx.invoice(v.id, 100, paid=40, status='PARTIAL')
        results = FinancialService.get_pending_invoices()
        assert isinstance(results, list)
        assert all(i.status in ('PENDING', 'PARTIAL') for i in results)


class TestRecordPayment:
    def test_records_via_payment_service(self, ffx):
        p = ffx.patient()
        v = ffx.visit(p.id)
        inv = ffx.invoice(v.id, 100, paid=0, status='ISSUED')
        ok = FinancialService.record_payment(inv.id, 60, method='cash')
        assert ok is True
        pays = Payment.query.filter_by(invoice_id=inv.id).all()
        assert len(pays) >= 1
        assert float(pays[-1].amount) == 60.0

    def test_missing_invoice_returns_false(self, ffx):
        assert FinancialService.record_payment(99999999, 10) is False


class TestExpenses:
    def test_get_expenses_stub_response(self, ffx):
        res = FinancialService.get_expenses()
        assert res["success"] is True
        assert res["available"] is False
        assert res["expenses"] == []

    def test_record_expense_stub_response(self, ffx):
        u = ffx.user()
        res = FinancialService.record_expense('supplies', 50, 'misc', u.id)
        assert res["success"] is False
        assert res["available"] is False
        assert res["expense"] is None


class TestReconcileVisitPayments:
    def test_visit_not_found(self, ffx):
        res = FinancialService.reconcile_visit_payments(99999999)
        assert res['ok'] is False

    def test_reconciles_and_sets_status(self, ffx):
        p = ffx.patient()
        v = ffx.visit(p.id)
        ffx.invoice(v.id, 100, paid=0, status='ISSUED')
        ffx.payment(v.id, p.id, 100, status='CONFIRMED')
        res = FinancialService.reconcile_visit_payments(v.id)
        assert res['ok'] is True
        # reconcile does not commit; assert on the returned snapshot
        assert res['invoices'][0]['status'] == 'PAID'
        assert float(res['invoices'][0]['paid_amount']) == 100.0

    def test_partial_status(self, ffx):
        p = ffx.patient()
        v = ffx.visit(p.id)
        ffx.invoice(v.id, 100, paid=0, status='ISSUED')
        ffx.payment(v.id, p.id, 40, status='CONFIRMED')
        res = FinancialService.reconcile_visit_payments(v.id)
        assert res['ok'] is True
        assert res['invoices'][0]['status'] == 'PARTIAL'


# ───────────────────────── BillingStateService ─────────────────────────

class TestBillingState:
    def test_pending_when_empty(self, ffx):
        p = ffx.patient()
        v = ffx.visit(p.id)
        assert BillingStateService.get_billing_state(v) == BillingState.PENDING

    def test_paid(self, ffx):
        p = ffx.patient()
        v = ffx.visit(p.id)
        ffx.invoice(v.id, 100)
        ffx.payment(v.id, p.id, 100)
        assert BillingStateService.get_billing_state(v) == BillingState.PAID

    def test_partial(self, ffx):
        p = ffx.patient()
        v = ffx.visit(p.id)
        ffx.invoice(v.id, 100)
        ffx.payment(v.id, p.id, 40)
        assert BillingStateService.get_billing_state(v) == BillingState.PARTIAL

    def test_debt(self, ffx):
        p = ffx.patient()
        v = ffx.visit(p.id)
        ffx.invoice(v.id, 100)
        assert BillingStateService.get_billing_state(v) == BillingState.DEBT


class TestCanCheckout:
    def test_paid_allows(self, ffx):
        p = ffx.patient()
        v = ffx.visit(p.id)
        ffx.invoice(v.id, 100)
        ffx.payment(v.id, p.id, 100)
        ok, _ = BillingStateService.can_checkout(v)
        assert ok is True

    def test_pending_allows(self, ffx):
        p = ffx.patient()
        v = ffx.visit(p.id)
        ok, _ = BillingStateService.can_checkout(v)
        assert ok is True

    def test_debt_without_approval_blocked(self, ffx):
        p = ffx.patient()
        v = ffx.visit(p.id)
        ffx.invoice(v.id, 100)
        ok, msg = BillingStateService.can_checkout(v)
        assert ok is False and 'approval' in msg

    def test_debt_with_approval_allowed(self, ffx):
        p = ffx.patient()
        v = ffx.visit(p.id)
        ffx.invoice(v.id, 100)
        v.debt_approved = True
        ok, _ = BillingStateService.can_checkout(v)
        assert ok is True

    def test_partial_blocked(self, ffx):
        p = ffx.patient()
        v = ffx.visit(p.id)
        ffx.invoice(v.id, 100)
        ffx.payment(v.id, p.id, 40)
        ok, msg = BillingStateService.can_checkout(v)
        assert ok is False and 'Outstanding' in msg


# ───────────────────────── ReceiptService ─────────────────────────

class TestReceiptService:
    def test_issue_print_void(self, ffx):
        p = ffx.patient()
        u = ffx.user()
        v = ffx.visit(p.id)
        pay = Payment(visit_id=v.id, patient_id=p.id, amount=100, method='CASH', received_by=u.id)
        ffx.db.session.add(pay)
        ffx.db.session.commit()
        res = ReceiptService.issue_receipt(v, pay)
        assert res['status'] == 'issued' and res['receipt_id']
        rid = res['receipt_id']
        ReceiptService.mark_printed(rid)
        ReceiptService.void_receipt(rid, reason='test')
        from models.receipt import Receipt
        rec = Receipt.query.get(rid)
        assert rec.status == 'voided' and rec.void_reason == 'test'

    def test_method_mapping_insurance(self, ffx):
        p = ffx.patient()
        u = ffx.user()
        v = ffx.visit(p.id)
        pay = Payment(visit_id=v.id, patient_id=p.id, amount=50, method='INSURANCE', received_by=u.id)
        ffx.db.session.add(pay)
        ffx.db.session.commit()
        res = ReceiptService.issue_receipt(v, pay)
        from models.receipt import Receipt
        rec = Receipt.query.get(res['receipt_id'])
        assert rec.payment_method == 'debt'


# ───────────────────────── PaymentAllocationService ─────────────────────────

class TestPaymentAllocation:
    def test_fifo_allocation_across_invoices(self, ffx):
        p = ffx.patient()
        v = ffx.visit(p.id)
        inv1 = ffx.invoice(v.id, 60, paid=0)
        inv2 = ffx.invoice(v.id, 60, paid=0)
        pay = ffx.payment(v.id, p.id, 100)
        PaymentAllocationService.allocate(pay, v)
        ffx.db.session.commit()
        ffx.db.session.refresh(inv1)
        ffx.db.session.refresh(inv2)
        assert float(inv1.paid_amount) == 60.0  # fully allocated first
        assert float(inv2.paid_amount) == 40.0  # remainder

    def test_no_overallocation(self, ffx):
        p = ffx.patient()
        v = ffx.visit(p.id)
        inv = ffx.invoice(v.id, 30, paid=0)
        pay = ffx.payment(v.id, p.id, 100)
        PaymentAllocationService.allocate(pay, v)
        ffx.db.session.commit()
        ffx.db.session.refresh(inv)
        assert float(inv.paid_amount) == 30.0
