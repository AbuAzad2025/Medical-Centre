"""
Refund Service - P3-006
Request → Approval → Execution workflow for payment refunds.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import func, select

from app.extensions import db
from utils.db_safety import safe_rollback
from utils.tenant_query import TenantContextError, get_tenant_record


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
        from models.payment import Payment, PaymentStatus
        from models.refund_request import RefundRequest, RefundStatus

        try:
            payment = get_tenant_record(Payment, payment_id)
        except TenantContextError:
            return False, 'الدفعة غير موجودة'
        if payment.tenant_id != tenant_id:
            return False, 'عدم تطابق المركز'
        if payment.status not in (PaymentStatus.CONFIRMED, PaymentStatus.PAID):
            return False, 'حالة الدفعة لا تسمح بالاسترداد'

        refund_amount = Decimal(str(amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if refund_amount <= 0:
            return False, 'يجب أن يكون مبلغ الاسترداد موجباً'
        payment_amount = Decimal(str(payment.amount or 0)).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        if refund_amount > payment_amount:
            return False, 'مبلغ الاسترداد يتجاوز المبلغ المدفوع'

        total_existing = db.session.execute(
            select(func.coalesce(func.sum(RefundRequest.amount), 0)).filter(
                RefundRequest.payment_id == payment.id,
                RefundRequest.status != RefundStatus.REJECTED,
            )
        ).scalar()
        total_existing_dec = Decimal(str(total_existing or 0)).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        if total_existing_dec + refund_amount > payment_amount:
            return False, 'إجمالي الاستردادات سيتجاوز المبلغ المدفوع'

        # Prevent duplicate pending requests for the same payment.
        existing = (
            db.session.execute(
                select(RefundRequest).filter_by(payment_id=payment.id, status=RefundStatus.PENDING)
            )
            .scalars()
            .first()
        )
        if existing:
            return False, 'A pending refund request already exists for this payment'

        try:
            request = RefundRequest(
                tenant_id=tenant_id,
                payment_id=payment.id,
                amount=refund_amount,
                reason=reason,
                requested_by=requested_by,
                status=RefundStatus.PENDING,
                requested_at=datetime.now(UTC),
            )
            db.session.add(request)
            db.session.flush()
            return True, request
        except Exception as e:
            safe_rollback(db.session, error_message='فشل إنشاء طلب الاسترداد')
            logging.exception('Error creating refund request: %s')
            return False, str(e)

    @staticmethod
    def approve_refund(
        refund_id: int,
        approved_by: int,
    ) -> tuple[bool, Any | str]:
        from models.payment import Payment
        from models.refund_request import RefundRequest, RefundStatus

        try:
            request = get_tenant_record(RefundRequest, refund_id)
        except TenantContextError:
            return False, 'طلب الاسترداد غير موجود'
        if request.status != RefundStatus.PENDING:
            return False, 'Refund request is not pending'
        payment = db.session.get(Payment, request.payment_id)
        if payment:
            total_existing = db.session.execute(
                select(func.coalesce(func.sum(RefundRequest.amount), 0)).filter(
                    RefundRequest.payment_id == payment.id,
                    RefundRequest.status != RefundStatus.REJECTED,
                )
            ).scalar()
            total_existing_dec = Decimal(str(total_existing or 0)).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            payment_amount = Decimal(str(payment.amount or 0)).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            if total_existing_dec > payment_amount:
                return False, 'إجمالي الاستردادات سيتجاوز المبلغ المدفوع'
        request.status = RefundStatus.APPROVED
        request.approved_by = approved_by
        request.approved_at = datetime.now(UTC)
        db.session.flush()
        return True, request

    @staticmethod
    def reject_refund(
        refund_id: int,
        rejected_by: int,
        reason: str = '',
    ) -> tuple[bool, Any | str]:
        from models.refund_request import RefundRequest, RefundStatus

        try:
            request = get_tenant_record(RefundRequest, refund_id)
        except TenantContextError:
            return False, 'طلب الاسترداد غير موجود'
        if request.status != RefundStatus.PENDING:
            return False, 'Refund request is not pending'

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
            return False, 'طلب الاسترداد غير موجود'
        if request.status != RefundStatus.APPROVED:
            return False, 'Refund request is not approved'

        try:
            payment = (
                db.session.execute(
                    select(Payment).filter_by(id=request.payment_id).with_for_update()
                )
                .scalars()
                .first()
            )
        except TenantContextError:
            return False, 'الدفعة الأصلية غير موجودة'
        if not payment:
            return False, 'الدفعة الأصلية غير موجودة'

        try:
            refund_amount = Decimal(str(request.amount)).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            total_executed = db.session.execute(
                select(func.coalesce(func.sum(RefundRequest.amount), 0)).filter(
                    RefundRequest.payment_id == payment.id,
                    RefundRequest.status == RefundStatus.EXECUTED,
                )
            ).scalar()
            total_executed_dec = Decimal(str(total_executed or 0)).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            payment_amount = Decimal(str(payment.amount or 0)).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            if total_executed_dec + refund_amount > payment_amount:
                return False, 'إجمالي الاستردادات سيتجاوز المبلغ المدفوع'

            if payment.visit_id:
                invoices = (
                    db.session.execute(
                        select(Invoice)
                        .filter_by(visit_id=payment.visit_id)
                        .order_by(Invoice.created_at.desc())
                        .with_for_update()
                    )
                    .scalars()
                    .all()
                )
                remaining = refund_amount
                for inv in invoices:
                    if remaining <= 0:
                        break
                    current_paid = Decimal(str(inv.paid_amount or 0)).quantize(
                        Decimal('0.01'), rounding=ROUND_HALF_UP
                    )
                    reversal = min(current_paid, remaining)
                    new_paid = current_paid - reversal
                    inv.paid_amount = float(new_paid)
                    remaining -= reversal
                    paid_dec = Decimal(str(inv.paid_amount or 0)).quantize(
                        Decimal('0.01'), rounding=ROUND_HALF_UP
                    )
                    total_dec = Decimal(str(inv.total_amount or 0)).quantize(
                        Decimal('0.01'), rounding=ROUND_HALF_UP
                    )
                    if paid_dec >= total_dec:
                        inv.status = 'PAID'
                    elif paid_dec > 0:
                        inv.status = 'PARTIAL'
                    else:
                        inv.status = 'ISSUED'

            payment.status = PaymentStatus.REFUNDED
            payment.cancelled_by = executed_by
            payment.cancelled_at = datetime.now(UTC)
            payment.cancellation_reason = f'Refund executed: {request.reason}'

            receipt = (
                db.session.execute(select(Receipt).filter_by(payment_id=payment.id))
                .scalars()
                .first()
            )
            if receipt:
                receipt.status = 'voided'
                receipt.void_reason = request.reason

            request.status = RefundStatus.EXECUTED
            request.executed_by = executed_by
            request.executed_at = datetime.now(UTC)

            # Post the reversing GL journal for the executed refund.
            try:
                from services.gl_service import GLService

                GLService.post_refund(payment, request)
            except Exception:
                logging.exception('GL posting failed for refund')

            db.session.flush()
            return True, request
        except Exception as e:
            safe_rollback(db.session, error_message='فشل تنفيذ الاسترداد')
            logging.exception('Error executing refund: %s')
            return False, str(e)


# Singleton
refund_service = RefundService()
