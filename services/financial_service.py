"""
Financial Service - Business logic for financial operations.
Extracted from routes/accountant/, routes/finance.py, routes/payment_routes.py.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select

from app.extensions import db
from utils.db_safety import safe_commit
from utils.tenant_query import TenantContextError, get_tenant_record


class FinancialService:
    """Centralized financial business logic"""

    @staticmethod
    def get_dashboard_stats(
        start_date: date | None = None, end_date: date | None = None, tenant_id: int | None = None
    ) -> dict:
        from flask import g

        from models.invoice import Invoice
        from models.payment import Payment

        if tenant_id is None:
            tenant_id = getattr(g, 'tenant_id', None) or getattr(
                getattr(g, 'current_tenant', None), 'id', None
            )
        try:
            q = Invoice.query.filter(Invoice.tenant_id == tenant_id) if tenant_id else Invoice.query
            if start_date:
                q = q.filter(Invoice.created_at >= start_date)
            if end_date:
                q = q.filter(Invoice.created_at <= end_date)
            total_billed = q.with_entities(
                func.coalesce(func.sum(Invoice.total_amount), 0)
            ).scalar()

            pq = (
                Payment.query.filter(Payment.tenant_id == tenant_id) if tenant_id else Payment.query
            )
            if start_date:
                pq = pq.filter(Payment.payment_date >= start_date)
            if end_date:
                pq = pq.filter(Payment.payment_date <= end_date)
            total_collected = pq.with_entities(func.coalesce(func.sum(Payment.amount), 0)).scalar()

            from models.expense import Expense

            eq = (
                Expense.query.filter(Expense.tenant_id == tenant_id) if tenant_id else Expense.query
            )
            if start_date:
                eq = eq.filter(Expense.expense_date >= start_date)
            if end_date:
                eq = eq.filter(Expense.expense_date <= end_date)
            total_expenses = eq.with_entities(func.coalesce(func.sum(Expense.amount), 0)).scalar()

            return {
                'total_billed': float(total_billed),
                'total_collected': float(total_collected),
                'total_expenses': float(total_expenses),
                'pending': float(total_billed) - float(total_collected),
            }
        except Exception:
            return {'total_billed': 0, 'total_collected': 0, 'total_expenses': 0, 'pending': 0}

    @staticmethod
    def reconcile_visit_payments(visit_id: int) -> dict:
        """P3-003: Recompute paid_amount for every invoice in a visit.

        Resets invoice allocations, re-applies confirmed visit payments in FIFO
        order, and updates invoice status (PAID/PARTIAL/ISSUED). The caller is
        responsible for committing the transaction.
        """
        from decimal import Decimal

        from models.invoice import Invoice
        from models.payment import Payment
        from models.visit import Visit
        from services.billing_state_service import PaymentAllocationService

        try:
            try:
                visit = get_tenant_record(Visit, visit_id)
            except TenantContextError:
                return {'ok': False, 'error': 'Visit not found'}

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
            for inv in invoices:
                inv.paid_amount = Decimal(0)

            payments = (
                db.session.execute(
                    select(Payment)
                    .filter_by(visit_id=visit.id, status='CONFIRMED')
                    .order_by(Payment.created_at.asc())
                )
                .scalars()
                .all()
            )
            for payment in payments:
                PaymentAllocationService.allocate(payment, visit)

            for inv in invoices:
                if Decimal(str(inv.paid_amount or 0)) >= Decimal(str(inv.total_amount or 0)):
                    inv.status = 'PAID'
                elif Decimal(str(inv.paid_amount or 0)) > 0:
                    inv.status = 'PARTIAL'
                else:
                    inv.status = 'ISSUED'

            return {'ok': True, 'invoices': [inv.to_dict() for inv in invoices]}
        except Exception as e:
            safe_commit(db.session, error_message='Error reconciling visit payments')
            logging.exception('Error reconciling visit payments: %s')
            return {'ok': False, 'error': str(e)}

    @staticmethod
    def get_revenue_by_period(
        period: str = 'monthly', limit: int = 12, tenant_id: int | None = None
    ) -> list:
        from flask import g

        from models.invoice import Invoice

        if tenant_id is None:
            tenant_id = getattr(g, 'tenant_id', None) or getattr(
                getattr(g, 'current_tenant', None), 'id', None
            )
        try:
            if period == 'daily':
                group_expr = func.date(Invoice.created_at)
            elif period == 'yearly':
                group_expr = func.year(Invoice.created_at)
            else:
                group_expr = func.date_format(Invoice.created_at, '%Y-%m')
            base = select(
                group_expr.label('period'),
                func.coalesce(func.sum(Invoice.total_amount), 0).label('amount'),
                func.count(Invoice.id).label('count'),
            )
            if tenant_id:
                base = base.where(Invoice.tenant_id == tenant_id)
            results = (
                db.session.execute(
                    base.group_by(group_expr).order_by(group_expr.desc()).limit(limit)
                )
                .scalars()
                .all()
            )
            return [
                {'period': str(r.period), 'amount': float(r.amount), 'count': r.count}
                for r in results
            ]
        except Exception:
            return []

    @staticmethod
    def create_invoice(patient_id: int, items: list[dict], notes: str | None = None) -> Any | None:
        from models.invoice import Invoice, InvoiceService
        from models.visit import Visit

        try:
            visit = (
                db.session.execute(
                    select(Visit).filter_by(patient_id=patient_id).order_by(Visit.created_at.desc())
                )
                .scalars()
                .first()
            )
            invoice_number = f'INV-{uuid.uuid4().hex[:8].upper()}'
            total = sum(item.get('price', 0) * item.get('quantity', 1) for item in items)
            invoice = Invoice(
                visit_id=visit.id if visit else None,
                total_amount=total,
                invoice_number=invoice_number,
                status='DRAFT',
            )
            db.session.add(invoice)
            db.session.flush()
            for item_data in items:
                item_total = item_data.get('price', 0) * item_data.get('quantity', 1)
                line = InvoiceService(
                    invoice_id=invoice.id,
                    service_code=item_data.get(
                        'service_code', f'SVC-{uuid.uuid4().hex[:6].upper()}'
                    ),
                    service_name=item_data.get('description', item_data.get('service_name', '')),
                    quantity=item_data.get('quantity', 1),
                    unit_price=item_data.get('price', 0),
                    total_price=item_total,
                    notes=notes or item_data.get('notes'),
                )
                db.session.add(line)
            if not safe_commit(db.session, error_message='Failed to create invoice'):
                return None
            return invoice
        except Exception:
            logging.exception('Error creating invoice: %s')
            return None

    @staticmethod
    def record_payment(
        invoice_id: int, amount: float, method: str = 'cash', notes: str | None = None
    ) -> bool:
        from models.invoice import Invoice
        from models.visit import Visit
        from services.payment_service import PaymentService

        try:
            try:
                invoice = get_tenant_record(Invoice, invoice_id)
            except TenantContextError:
                return False
            visit = get_tenant_record(Visit, invoice.visit_id) if invoice.visit_id else None
            method_upper = (method or 'cash').upper()
            ok, result = PaymentService.create_payment(
                tenant_id=getattr(invoice, 'tenant_id', None)
                or (visit.tenant_id if visit else None),
                operation_type='invoice_payment',
                idempotency_key=None,
                patient_id=visit.patient_id if visit else None,
                visit_id=invoice.visit_id,
                invoice_id=invoice.id,
                method=method_upper,
                amount=amount,
                notes=notes,
            )
            if not ok:
                logging.error(f'Error recording payment: {result}')
                return False
            return safe_commit(db.session, error_message='Failed to record payment')
        except Exception:
            logging.exception('Error recording payment: %s')
            return False

    @staticmethod
    def get_pending_invoices(limit: int = 50, tenant_id: int | None = None) -> list:
        from flask import g

        from models.invoice import Invoice

        if tenant_id is None:
            tenant_id = getattr(g, 'tenant_id', None) or getattr(
                getattr(g, 'current_tenant', None), 'id', None
            )
        q = select(Invoice).filter(Invoice.status.in_(['PENDING', 'PARTIAL']))
        if tenant_id:
            q = q.filter(Invoice.tenant_id == tenant_id)
        return db.session.execute(q.order_by(Invoice.created_at.asc()).limit(limit)).scalars().all()

    @staticmethod
    def get_expenses(
        category: str | None = None, limit: int = 100, tenant_id: int | None = None
    ) -> dict:
        from flask import g

        from models.expense import Expense

        if tenant_id is None:
            tenant_id = getattr(g, 'tenant_id', None) or getattr(
                getattr(g, 'current_tenant', None), 'id', None
            )
        try:
            query = select(Expense)
            if tenant_id:
                query = query.filter(Expense.tenant_id == tenant_id)
            if category:
                query = query.filter(Expense.category == category)
            query = query.limit(max(1, min(limit, 500)))
            rows = db.session.execute(query).scalars().all()
            return {
                'success': True,
                'available': True,
                'expenses': [row.to_dict() for row in rows],
                'category': category,
                'limit': limit,
            }
        except Exception as e:
            logging.exception('Error loading expenses: %s')
            return {
                'success': False,
                'available': True,
                'expenses': [],
                'message': str(e),
                'category': category,
                'limit': limit,
            }

    @staticmethod
    def record_expense(
        description: str,
        amount: float,
        category: str,
        recorded_by: int,
        *,
        expense_date: date | None = None,
    ) -> dict:
        from models.expense import Expense

        try:
            if amount <= 0:
                return {
                    'success': False,
                    'available': True,
                    'expense': None,
                    'message': 'amount_must_be_positive',
                }
            expense = Expense(
                description=description,
                amount=Decimal(str(amount)),
                category=category,
                recorded_by_id=recorded_by,
                expense_date=expense_date or date.today(),
                status='RECORDED',
            )
            db.session.add(expense)
            try:
                db.session.flush()
                from services.gl_service import GLService

                GLService.post_expense(expense)
            except Exception:
                logging.exception('GL posting failed for expense')
            if not safe_commit(db.session, error_message='Failed to record expense'):
                return {
                    'success': False,
                    'available': True,
                    'expense': None,
                    'message': 'database_error',
                }
            return {
                'success': True,
                'available': True,
                'expense': expense.to_dict(),
                'message': None,
            }
        except Exception as e:
            logging.exception('Error recording expense: %s')
            return {'success': False, 'available': True, 'expense': None, 'message': str(e)}

    @staticmethod
    def create_insurance_claim(invoice_id: int, tenant_id: int, user_id: int) -> dict:
        """Create an insurance claim from an issued invoice.

        Builds a claim record linked to the invoice and its visit.
        The claim starts in DRAFT status and must be submitted separately.
        """
        from models.insurance import InsuranceClaim
        from models.invoice import Invoice
        from models.visit import Visit

        try:
            invoice = (
                db.session.execute(
                    select(Invoice).filter(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
                )
                .scalars()
                .first()
            )
            if not invoice:
                return {'ok': False, 'error': 'Invoice not found'}

            if invoice.status != 'ISSUED':
                return {
                    'ok': False,
                    'error': f'Invoice status "{invoice.status}" is not ISSUED',
                }

            visit = (
                db.session.execute(select(Visit).filter(Visit.id == invoice.visit_id).limit(1))
                .scalars()
                .first()
            )

            company_id = None
            if visit and getattr(visit, 'insurance_company_id', None):
                company_id = visit.insurance_company_id

            claim_number = f'CLM-{invoice_id}-{int(datetime.now(UTC).timestamp())}'
            claim = InsuranceClaim(
                tenant_id=tenant_id,
                company_id=company_id,
                visit_id=invoice.visit_id,
                invoice_id=invoice.id,
                claim_number=claim_number,
                status='DRAFT',
                total_claim=invoice.total_amount,
                approved_amount=Decimal(0),
                patient_share_amount=invoice.total_amount,
                insurance_share_amount=Decimal(0),
            )
            db.session.add(claim)
            if not safe_commit(db.session, error_message='Failed to create insurance claim'):
                return {'ok': False, 'error': 'database_error'}
            return {'ok': True, 'claim_id': claim.id, 'claim_number': claim_number}
        except Exception as e:
            logging.exception('Error creating insurance claim')
            return {'ok': False, 'error': str(e)}

    @staticmethod
    def update_claim_status(
        claim_id: int,
        status: str,
        approved_amount: Decimal | None = None,
        notes: str | None = None,
        tenant_id: int | None = None,
    ) -> dict:
        """Adjudicate or settle an insurance claim.

        Updates the claim status, approved amount, and insurance/patient
        share amounts based on the new status.
        """
        from app.shared.enums import InsuranceClaimStatus
        from models.insurance import InsuranceClaim

        try:
            claim = (
                db.session.execute(select(InsuranceClaim).filter(InsuranceClaim.id == claim_id))
                .scalars()
                .first()
            )
            if not claim:
                return {'ok': False, 'error': 'Claim not found'}

            if tenant_id and claim.tenant_id != tenant_id:
                return {'ok': False, 'error': 'Tenant mismatch'}

            valid_statuses = {
                InsuranceClaimStatus.DRAFT,
                InsuranceClaimStatus.SUBMITTED,
                InsuranceClaimStatus.UNDER_REVIEW,
                InsuranceClaimStatus.APPROVED,
                InsuranceClaimStatus.PARTIALLY_APPROVED,
                InsuranceClaimStatus.REJECTED,
                InsuranceClaimStatus.SETTLED,
            }
            if status not in valid_statuses:
                return {
                    'ok': False,
                    'error': f'Invalid status "{status}"',
                }

            if status == InsuranceClaimStatus.SETTLED:
                claim.settle(approved_amount or claim.approved_amount)
            else:
                claim.adjudicate(
                    approved_amount or claim.approved_amount,
                    status,
                    notes,
                )

            if not safe_commit(db.session, error_message='Failed to update claim status'):
                return {'ok': False, 'error': 'database_error'}
            return {'ok': True, 'claim_id': claim.id, 'status': claim.status}
        except Exception as e:
            logging.exception('Error updating claim status')
            return {'ok': False, 'error': str(e)}


# Singleton
financial_service = FinancialService()
