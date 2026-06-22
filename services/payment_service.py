"""
Payment Service - Idempotency-aware payment creation.
P3-001: Scoped idempotency keyed by tenant_id + operation_type + idempotency_key.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app_factory import db
from sqlalchemy import and_


class PaymentService:
    """Centralized payment business logic with idempotency support."""

    @staticmethod
    def create_payment(
        *,
        tenant_id: int | None,
        operation_type: str,
        idempotency_key: str | None,
        patient_id: int | None = None,
        visit_id: int | None = None,
        invoice_id: int | None = None,
        method: str = "CASH",
        amount: Decimal | float | str,
        currency: str = "ILS",
        status: str = "CONFIRMED",
        reference: str | None = None,
        received_by: int | None = None,
        notes: str | None = None,
    ) -> tuple[bool, Any | str]:
        """Create a Payment with idempotency protection.

        If `idempotency_key` is provided and a matching payment already exists
        for the same tenant + operation_type + key, the existing payment is
        returned instead of creating a duplicate.

        Returns (success, Payment|error_message).
        """
        from models.payment import Payment

        if not operation_type:
            return False, "operation_type is required"

        if idempotency_key:
            existing = Payment.query.filter(
                and_(
                    Payment.tenant_id == tenant_id,
                    Payment.operation_type == operation_type,
                    Payment.idempotency_key == idempotency_key,
                )
            ).first()
            if existing:
                return True, existing

        try:
            payment = Payment(
                tenant_id=tenant_id,
                operation_type=operation_type,
                idempotency_key=idempotency_key,
                patient_id=patient_id,
                visit_id=visit_id,
                invoice_id=invoice_id,
                method=method,
                amount=Decimal(str(amount)),
                currency=currency,
                status=status,
                reference=reference,
                received_by=received_by,
                notes=notes,
                payment_date=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.session.add(payment)
            db.session.flush()

            # P3-002: allocate confirmed payments against visit invoices within
            # the same transaction boundary.
            if status == "CONFIRMED" and visit_id:
                from models.visit import Visit
                from services.billing_state_service import PaymentAllocationService
                visit = db.session.get(Visit, visit_id)
                if visit:
                    PaymentAllocationService.allocate(payment, visit)

            return True, payment
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating payment: {str(e)}")
            return False, str(e)


# Singleton
payment_service = PaymentService()
