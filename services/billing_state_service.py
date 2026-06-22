"""
BillingStateService — unified billing state management
"""
from decimal import Decimal
from datetime import datetime, timezone
from flask import g
from app.extensions import db
from app.shared.enums import BillingState, PaymentStatus


class BillingStateService:
    @staticmethod
    def get_billing_state(visit) -> str:
        from models.payment import Payment
        from models.invoice import Invoice
        payments = Payment.query.filter_by(visit_id=visit.id).all()
        invoices = Invoice.query.filter_by(visit_id=visit.id).all()
        total_paid = sum(float(p.amount or 0) for p in payments if p.status == PaymentStatus.CONFIRMED)
        total_invoiced = sum(float(i.total or 0) for i in invoices)
        if total_paid <= 0 and total_invoiced <= 0:
            return BillingState.PENDING
        if total_paid >= total_invoiced and total_invoiced > 0:
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
            return False, "Debt requires approval"
        if state == BillingState.PARTIAL:
            return False, "Outstanding balance remaining"
        return True, None


class ReceiptService:
    @staticmethod
    def issue_receipt(visit, payment) -> dict:
        from models.receipt import Receipt
        receipt = Receipt(
            tenant_id=getattr(g, 'tenant_id', None),
            visit_id=visit.id,
            payment_id=payment.id,
            patient_id=visit.patient_id,
            amount=payment.amount,
            issued_at=datetime.now(timezone.utc),
            status='issued',
        )
        db.session.add(receipt)
        db.session.commit()
        return {"receipt_id": receipt.id, "status": "issued"}

    @staticmethod
    def mark_printed(receipt_id: int):
        from models.receipt import Receipt
        receipt = Receipt.query.get(receipt_id)
        if receipt:
            receipt.status = 'printed'
            receipt.printed_at = datetime.now(timezone.utc)
            db.session.commit()

    @staticmethod
    def void_receipt(receipt_id: int, reason: str = ""):
        from models.receipt import Receipt
        receipt = Receipt.query.get(receipt_id)
        if receipt:
            receipt.status = 'voided'
            receipt.void_reason = reason
            db.session.commit()


class PaymentAllocationService:
    @staticmethod
    def allocate(payment, visit):
        """Allocate a confirmed payment against visit invoices (FIFO).

        P3-002: This method intentionally does NOT commit; it is the caller's
        responsibility to commit inside the same transaction boundary as the
        payment creation.
        """
        from models.invoice import Invoice
        invoices = Invoice.query.filter_by(visit_id=visit.id).order_by(Invoice.created_at.asc()).all()
        remaining = Decimal(str(payment.amount))
        for inv in invoices:
            due = Decimal(str(inv.total_amount or 0)) - Decimal(str(inv.paid_amount or 0))
            if due > 0:
                alloc = min(remaining, due)
                inv.paid_amount = float(Decimal(str(inv.paid_amount or 0)) + alloc)
                remaining -= alloc
                if remaining <= 0:
                    break
