"""
Refund Service - P3-006
Request → Approval → Execution workflow for payment refunds.
"""
from __future__ import annotations
from sqlalchemy import select, func

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.extensions import db
from utils.db_safety import safe_rollback
from utils.tenant_query import get_tenant_record, TenantContextError


class RefundService:
    """Centralized refund business logic."""

    @staticmethod
    def request_refund(
        tenant_id: int,
        payment_id: int,
        amount: Decimal | float | str,
        reason: str,
        requested_by: int | None = None,
    ) -> tuple[bool, Any | str]:
        from models.invoice import Invoice
        from models.payment import Payment, PaymentStatus
        from models.refund_request import RefundRequest, RefundStatus

        try:
            payment = get_tenant_record(Payment, payment_id)
        except TenantContextError:
            return False, "Payment not found"
        if payment.tenant_id != tenant_id:
            return False, "Tenant mismatch"
        if payment.status not in (PaymentStatus.CONFIRMED, PaymentStatus.PAID):
            return False, "Payment is not in a refundable state"

        refund_amount = Decimal(str(amount))
        if refund_amount <= 0:
            return False, "Refund amount must be positive"
        if refund_amount > Decimal(str(payment.amount or 0)):
            return False, "Refund amount exceeds payment amount"

        # Prevent over-refunding: sum all non-rejected requests for this payment.
        total_existing = db.session.execute(
            select(func.coalesce(func.sum(RefundRequest.amount), 0)).filter(
                RefundRequest.payment_id == payment.id,
                RefundRequest.status != RefundStatus.REJECTED,
            )
        ).scalar()
        if Decimal(str(total_existing or 0)) + refund_amount > Decimal(str(payment.amount or 0)):
            return False, "Cumulative refund amount would exceed payment amount"

        # Prevent duplicate pending requests for the same payment.
        existing = db.session.execute(select(RefundRequest).filter_by(
            payment_id=payment.id, status=RefundStatus.PENDING
        )).scalars().first()
        if existing:
            return False, "A pending refund request already exists for this payment"

        try:
            request = RefundRequest(
                tenant_id=tenant_id,
                payment_id=payment.id,
                amount=refund_amount,
                reason=reason,
                requested_by=requested_by,
                status=RefundStatus.PENDING,
                requested_at=datetime.now(timezone.utc),
            )
            db.session.add(request)
            db.session.flush()
            return True, request
        except Exception as e:
            safe_rollback(db.session, error_message="فشل إنشاء طلب الاسترداد")
            logging.error(f"Error creating refund request: {str(e)}")
            return False, str(e)

    @staticmethod
    def approve_refund(
        refund_id: int,
        approved_by: int,
    ) -> tuple[bool, Any | str]:
        from models.refund_request import RefundRequest, RefundStatus

        try:
            request = get_tenant_record(RefundRequest, refund_id)
        except TenantContextError:
            return False, "Refund request not found"
        if request.status != RefundStatus.PENDING:
            return False, "Refund request is not pending"

        request.status = RefundStatus.APPROVED
        request.approved_by = approved_by
        request.approved_at = datetime.now(timezone.utc)
        db.session.flush()
        return True, request

    @staticmethod
    def reject_refund(
        refund_id: int,
        rejected_by: int,
        reason: str = "",
    ) -> tuple[bool, Any | str]:
        from models.refund_request import RefundRequest, RefundStatus

        try:
            request = get_tenant_record(RefundRequest, refund_id)
        except TenantContextError:
            return False, "Refund request not found"
        if request.status != RefundStatus.PENDING:
            return False, "Refund request is not pending"

        request.status = RefundStatus.REJECTED
        request.notes = reason
        db.session.flush()
        return True, request

    @staticmethod
    def execute_refund(
        refund_id: int,
        executed_by: int,
    ) -> tuple[bool, Any | str]:
        """Execute an approved refund.

        - Marks the original payment as REFUNDED.
        - Reverses allocation by reducing invoice paid_amount amounts
          (reverse FIFO: newest invoices first).
        - Voids any receipt tied to the payment.
        """
        from models.invoice import Invoice
        from models.payment import Payment, PaymentStatus
        from models.receipt import Receipt
        from models.refund_request import RefundRequest, RefundStatus

        try:
            request = get_tenant_record(RefundRequest, refund_id)
        except TenantContextError:
            return False, "Refund request not found"
        if request.status != RefundStatus.APPROVED:
            return False, "Refund request is not approved"

        try:
            payment = db.session.execute(
                select(Payment).filter_by(id=request.payment_id).with_for_update()
            ).scalars().first()
        except TenantContextError:
            return False, "Original payment not found"
        if not payment:
            return False, "Original payment not found"

        try:
            refund_amount = Decimal(str(request.amount))
            # Re-check cumulative limit under row lock.
            total_executed = db.session.execute(
                select(func.coalesce(func.sum(RefundRequest.amount), 0)).filter(
                    RefundRequest.payment_id == payment.id,
                    RefundRequest.status == RefundStatus.EXECUTED,
                )
            ).scalar()
            if Decimal(str(total_executed or 0)) + refund_amount > Decimal(str(payment.amount or 0)):
                return False, "Cumulative refund amount would exceed payment amount"

            if payment.visit_id:
                invoices = db.session.execute(select(Invoice).filter_by(visit_id=payment.visit_id).order_by(
                    Invoice.created_at.desc()
                )).scalars().all()
                remaining = refund_amount
                for inv in invoices:
                    if remaining <= 0:
                        break
                    current_paid = Decimal(str(inv.paid_amount or 0))
                    reversal = min(current_paid, remaining)
                    inv.paid_amount = float(current_paid - reversal)
                    remaining -= reversal

                    # Update invoice status based on remaining paid amount.
                    if Decimal(str(inv.paid_amount or 0)) >= Decimal(str(inv.total_amount or 0)):
                        inv.status = "PAID"
                    elif Decimal(str(inv.paid_amount or 0)) > 0:
                        inv.status = "PARTIAL"
                    else:
                        inv.status = "ISSUED"

            payment.status = PaymentStatus.REFUNDED
            payment.cancelled_by = executed_by
            payment.cancelled_at = datetime.now(timezone.utc)
            payment.cancellation_reason = f"Refund executed: {request.reason}"

            receipt = db.session.execute(select(Receipt).filter_by(payment_id=payment.id)).scalars().first()
            if receipt:
                receipt.status = "voided"
                receipt.void_reason = request.reason

            request.status = RefundStatus.EXECUTED
            request.executed_by = executed_by
            request.executed_at = datetime.now(timezone.utc)

            db.session.flush()
            return True, request
        except Exception as e:
            safe_rollback(db.session, error_message="فشل تنفيذ الاسترداد")
            logging.error(f"Error executing refund: {str(e)}")
            return False, str(e)


# Singleton
refund_service = RefundService()
