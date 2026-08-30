"""
BillingStateService — unified billing state management
"""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from app.extensions import db
from app.shared.enums import BillingState, PaymentStatus
from utils.db_safety import safe_commit
from utils.tenant_query import get_tenant_record


class BillingStateService:
    @staticmethod
    def get_billing_state(visit) -> str:
        from models.invoice import Invoice
        from models.payment import Payment

        payments = db.session.execute(select(Payment).filter_by(visit_id=visit.id)).scalars().all()
        invoices = db.session.execute(select(Invoice).filter_by(visit_id=visit.id)).scalars().all()
        total_paid = sum(
            float(p.amount or 0) for p in payments if p.status == PaymentStatus.CONFIRMED
        )
        total_invoiced = sum(float(i.total_amount or 0) for i in invoices)
        if total_paid <= 0 and total_invoiced <= 0:
            return BillingState.PENDING
        if total_paid >= total_invoiced > 0:
            return BillingState.PAID
        if total_paid > total_invoiced:
            return BillingState.PAID
        if total_paid > 0 and total_paid < total_invoiced:
            return BillingState.PARTIAL
        if total_invoiced > 0 and total_paid <= 0:
            return BillingState.DEBT
        return BillingState.PENDING

    @staticmethod
    def can_checkout(visit) -> tuple[bool, str | None]:
        state = BillingStateService.get_billing_state(visit)
        if state in (BillingState.PAID, BillingState.PENDING):
            return True, None
        if state == BillingState.DEBT:
            if getattr(visit, 'debt_approved', False):
                return True, None
            return False, 'Debt requires approval'
        if state == BillingState.PARTIAL:
            return False, 'Outstanding balance remaining'
        return True, None


class ReceiptService:
    """P3-004: Issue, print, and void receipts bound to a payment."""

    # Map Payment.method values to Receipt.payment_method constraint values.
    _METHOD_MAP = {
        'CASH': 'cash',
        'CARD': 'card',
        'WIRE': 'card',
        'INSURANCE': 'debt',
        'FORCE': 'cash',
    }

    @staticmethod
    def issue_receipt(visit, payment) -> dict:
        from decimal import Decimal

        from models.receipt import Receipt

        receipt = Receipt(
            tenant_id=visit.tenant_id,
            visit_id=visit.id,
            patient_id=visit.patient_id,
            payment_id=payment.id,
            total_amount=Decimal(str(payment.amount or 0)),
            paid_amount=Decimal(str(payment.amount or 0)),
            remaining_amount=Decimal(0),
            payment_method=ReceiptService._METHOD_MAP.get(str(payment.method).upper(), 'cash'),
            payment_status='PAID',
            status='issued',
            created_by=payment.received_by,
            created_at=datetime.now(UTC),
        )
        receipt.generate_receipt_number()
        db.session.add(receipt)
        safe_commit(db.session, error_message='Failed to issue receipt', reraise=True)
        return {'receipt_id': receipt.id, 'status': 'issued'}

    @staticmethod
    def mark_printed(receipt_id: int):
        from models.receipt import Receipt

        receipt = get_tenant_record(Receipt, receipt_id)
        if receipt:
            receipt.status = 'printed'
            receipt.is_printed = True
            receipt.printed_at = datetime.now(UTC)
            safe_commit(db.session, error_message='Failed to mark receipt printed', reraise=True)

    @staticmethod
    def void_receipt(receipt_id: int, reason: str = ''):
        from models.receipt import Receipt

        receipt = get_tenant_record(Receipt, receipt_id)
        if receipt:
            receipt.status = 'voided'
            receipt.void_reason = reason
            safe_commit(db.session, error_message='Failed to void receipt', reraise=True)


class PaymentAllocationService:
    @staticmethod
    def allocate(payment, visit):
        """Allocate a confirmed payment against visit invoices (FIFO).

        P3-002: This method intentionally does NOT commit; it is the caller's
        responsibility to commit inside the same transaction boundary as the
        payment creation.

        FIX: Uses SELECT FOR UPDATE to prevent race conditions in concurrent payments.
        """
        from models.invoice import Invoice

        invoices = (
            db.session.execute(
                select(Invoice)
                .filter_by(visit_id=visit.id)
                .order_by(Invoice.created_at.asc())
                .with_for_update()
            )
            .scalars()
            .all()
        )
        remaining = Decimal(str(payment.amount))
        allocated = Decimal(0)
        for inv in invoices:
            due = Decimal(str(inv.total_amount or 0)) - Decimal(str(inv.paid_amount or 0))
            if due > 0:
                alloc = min(remaining, due)
                new_paid = Decimal(str(inv.paid_amount or 0)) + alloc
                inv.paid_amount = float(new_paid)
                remaining -= alloc
                allocated += alloc
                if remaining <= 0:
                    break
        return float(allocated)
