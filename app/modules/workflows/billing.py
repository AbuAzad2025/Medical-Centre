"""
BillingService — invoice posting, payments, refunds, credit notes
"""
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional
from app.extensions import db

class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    POSTED = "posted"
    PAID = "paid"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class BillingService:
    """All financial mutations MUST go through this service."""

    @staticmethod
    def create_invoice(visit_id: int, items: list[dict], created_by: int) -> object:
        from models.invoice import Invoice, InvoiceService
        inv = Invoice(visit_id=visit_id, status=InvoiceStatus.DRAFT, created_by=created_by)
        db.session.add(inv)
        db.session.flush()
        total = Decimal("0.00")
        for it in items:
            line = InvoiceService(
                invoice_id=inv.id,
                service_name=it.get("name"),
                quantity=it.get("quantity", 1),
                unit_price=Decimal(str(it.get("unit_price", 0))),
                total_price=Decimal(str(it.get("unit_price", 0))) * it.get("quantity", 1),
            )
            db.session.add(line)
            total += line.total_price
        inv.total_amount = total
        return inv

    @staticmethod
    def post_invoice(invoice, posted_by: int) -> None:
        if invoice.status != InvoiceStatus.DRAFT:
            raise ValueError("Only DRAFT invoices can be posted")
        invoice.status = InvoiceStatus.POSTED
        invoice.posted_at = datetime.now(timezone.utc)
        invoice.posted_by = posted_by
        db.session.add(invoice)

    @staticmethod
    def record_payment(invoice, amount: Decimal, method: str, reference: Optional[str] = None,
                        received_by: Optional[int] = None) -> object:
        from models.payment import Payment
        if invoice.status in (InvoiceStatus.CANCELLED, InvoiceStatus.REFUNDED):
            raise ValueError("Cannot pay a cancelled/refunded invoice")

        payment = Payment(
            invoice_id=invoice.id,
            amount=amount,
            payment_method=method,
            reference_number=reference,
            received_by=received_by,
        )
        db.session.add(payment)

        # Update invoice balance
        invoice.paid_amount = (invoice.paid_amount or Decimal("0.00")) + amount
        if invoice.paid_amount >= invoice.total_amount:
            invoice.status = InvoiceStatus.PAID
        else:
            invoice.status = InvoiceStatus.PARTIAL
        invoice.updated_at = datetime.now(timezone.utc)
        db.session.add(invoice)
        return payment

    @staticmethod
    def refund_payment(payment, amount: Decimal, reason: str, performed_by: int) -> object:
        from models.payment import Payment
        if amount > payment.amount:
            raise ValueError("Refund cannot exceed original payment")

        refund = Payment(
            invoice_id=payment.invoice_id,
            amount=-amount,
            payment_method=payment.payment_method,
            reference_number=f"REFUND:{payment.id}",
            notes=reason,
            received_by=performed_by,
        )
        db.session.add(refund)

        invoice = payment.invoice
        invoice.paid_amount = (invoice.paid_amount or Decimal("0.00")) - amount
        if invoice.paid_amount <= 0:
            invoice.status = InvoiceStatus.REFUNDED
        else:
            invoice.status = InvoiceStatus.PARTIAL if invoice.paid_amount < invoice.total_amount else InvoiceStatus.PAID
        db.session.add(invoice)
        return refund
