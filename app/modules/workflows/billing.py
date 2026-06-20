"""
BillingService — invoice lifecycle and posting
"""
from datetime import datetime, timezone
from typing import Any
from app.shared.enums import InvoiceStatus


class _BillingServiceDeprecated:
    """Legacy billing posting — maintained for test compatibility."""

    @staticmethod
    def post_invoice(invoice: Any, user_id: int) -> None:
        if invoice.status != InvoiceStatus.DRAFT:
            raise ValueError("Only DRAFT invoices can be posted")
        invoice.status = InvoiceStatus.POSTED
        invoice.posted_at = datetime.now(timezone.utc)
