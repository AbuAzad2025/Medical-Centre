"""
Payment Service - Idempotency-aware payment creation.
P3-001: Scoped idempotency keyed by tenant_id + operation_type + idempotency_key.
"""

from __future__ import annotations

import logging
import time as _time
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError

from app.core.rate_limiter import IdempotencyLock
from app.extensions import db
from utils.db_safety import safe_rollback
from utils.tenant_query import TenantContextError, get_tenant_record


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
        method: str = 'CASH',
        amount: Decimal | float | str,
        currency: str = 'ILS',
        status: str = 'CONFIRMED',
        reference: str | None = None,
        received_by: int | None = None,
        notes: str | None = None,
    ) -> tuple[bool, Any | str]:
        """Create a Payment with idempotency protection.

        If `idempotency_key` is provided and a matching payment already exists
        for the same tenant + operation_type + key, the existing payment is
        returned instead of creating a duplicate.

        A distributed lock (Redis → in-memory fallback) prevents concurrent
        requests with the same key from racing into an IntegrityError.

        Returns (success, Payment|error_message).
        """
        from models.payment import Payment

        if not operation_type:
            return False, 'operation_type is required'

        if idempotency_key:
            lock_key = f'{tenant_id or "global"}:{operation_type}:{idempotency_key}'
            lock = IdempotencyLock(timeout_seconds=30)

            if not lock.acquire(lock_key):
                # Another worker holds the lock – wait briefly then fetch existing.
                _time.sleep(0.15)
                existing = (
                    db.session.execute(
                        select(Payment).filter(
                            and_(
                                Payment.tenant_id == tenant_id,
                                Payment.operation_type == operation_type,
                                Payment.idempotency_key == idempotency_key,
                            )
                        )
                    )
                    .scalars()
                    .first()
                )
                if existing:
                    return True, existing
                # One retry after the short sleep
                if not lock.acquire(lock_key):
                    return False, 'Idempotency conflict: unable to acquire lock after retry'

            try:
                # Double-check under lock with SELECT FOR UPDATE for extra safety
                existing = (
                    db.session.execute(
                        select(Payment)
                        .filter(
                            and_(
                                Payment.tenant_id == tenant_id,
                                Payment.operation_type == operation_type,
                                Payment.idempotency_key == idempotency_key,
                            )
                        )
                        .with_for_update()
                    )
                    .scalars()
                    .first()
                )
                if existing:
                    return True, existing

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
                    payment_date=datetime.now(UTC),
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
                db.session.add(payment)
                db.session.flush()

                # P3-002: allocate confirmed payments against visit invoices within
                # the same transaction boundary.
                if status == 'CONFIRMED' and visit_id:
                    from models.visit import Visit
                    from services.billing_state_service import PaymentAllocationService

                    try:
                        visit = get_tenant_record(Visit, visit_id)
                    except TenantContextError:
                        visit = None
                    if visit:
                        PaymentAllocationService.allocate(payment, visit)

                return True, payment
            except IntegrityError as e:
                safe_rollback(db.session, error_message='Payment idempotency conflict')
                # Safety net: if the lock somehow didn't prevent the race.
                existing = (
                    db.session.execute(
                        select(Payment).filter(
                            and_(
                                Payment.tenant_id == tenant_id,
                                Payment.operation_type == operation_type,
                                Payment.idempotency_key == idempotency_key,
                            )
                        )
                    )
                    .scalars()
                    .first()
                )
                if existing:
                    return True, existing
                logging.exception(f'Payment IntegrityError (non-idempotency): {e!s}')
                return False, str(e)
            except Exception as e:
                safe_rollback(db.session, error_message='فشل إنشاء الدفعة')
                logging.exception(f'Error creating payment: {e!s}')
                return False, str(e)
            finally:
                lock.release(lock_key)

        # No idempotency key – standard create path (no lock needed)
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
                payment_date=datetime.now(UTC),
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            db.session.add(payment)
            db.session.flush()

            if status == 'CONFIRMED' and visit_id:
                from models.visit import Visit
                from services.billing_state_service import PaymentAllocationService

                try:
                    visit = get_tenant_record(Visit, visit_id)
                except TenantContextError:
                    visit = None
                if visit:
                    PaymentAllocationService.allocate(payment, visit)

            return True, payment
        except Exception as e:
            safe_rollback(db.session, error_message='فشل إنشاء الدفعة')
            logging.exception(f'Error creating payment: {e!s}')
            return False, str(e)


# Singleton
payment_service = PaymentService()
