"""
Financial Service - Business logic for financial operations.
Extracted from routes/accountant/, routes/finance.py, routes/payment_routes.py.
"""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from app_factory import db
from sqlalchemy import func


class FinancialService:
    """Centralized financial business logic"""

    @staticmethod
    def get_dashboard_stats(start_date: date | None = None, end_date: date | None = None) -> dict:
        from models.invoice import Invoice
        from models.payment import Payment
        try:
            q = Invoice.query
            if start_date:
                q = q.filter(Invoice.created_at >= start_date)
            if end_date:
                q = q.filter(Invoice.created_at <= end_date)
            total_billed = q.with_entities(func.coalesce(func.sum(Invoice.total_amount), 0)).scalar()

            pq = Payment.query
            if start_date:
                pq = pq.filter(Payment.payment_date >= start_date)
            if end_date:
                pq = pq.filter(Payment.payment_date <= end_date)
            total_collected = pq.with_entities(func.coalesce(func.sum(Payment.amount), 0)).scalar()

            return {
                "total_billed": float(total_billed),
                "total_collected": float(total_collected),
                "total_expenses": 0,
                "pending": float(total_billed) - float(total_collected),
            }
        except Exception:
            return {"total_billed": 0, "total_collected": 0, "total_expenses": 0, "pending": 0}

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
            visit = db.session.get(Visit, visit_id)
            if not visit:
                return {"ok": False, "error": "Visit not found"}

            invoices = Invoice.query.filter_by(visit_id=visit.id).order_by(Invoice.created_at.asc()).all()
            for inv in invoices:
                inv.paid_amount = Decimal(0)

            payments = Payment.query.filter_by(visit_id=visit.id, status="CONFIRMED").order_by(
                Payment.created_at.asc()
            ).all()
            for payment in payments:
                PaymentAllocationService.allocate(payment, visit)

            for inv in invoices:
                if Decimal(str(inv.paid_amount or 0)) >= Decimal(str(inv.total_amount or 0)):
                    inv.status = "PAID"
                elif Decimal(str(inv.paid_amount or 0)) > 0:
                    inv.status = "PARTIAL"
                else:
                    inv.status = "ISSUED"

            return {"ok": True, "invoices": [inv.to_dict() for inv in invoices]}
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error reconciling visit payments: {str(e)}")
            return {"ok": False, "error": str(e)}

    @staticmethod
    def get_revenue_by_period(period: str = "monthly", limit: int = 12) -> list:
        from models.invoice import Invoice
        try:
            if period == "daily":
                group_expr = func.date(Invoice.created_at)
            elif period == "yearly":
                group_expr = func.year(Invoice.created_at)
            else:
                group_expr = func.date_format(Invoice.created_at, "%Y-%m")
            results = db.session.query(
                group_expr.label("period"),
                func.coalesce(func.sum(Invoice.total_amount), 0).label("amount"),
                func.count(Invoice.id).label("count"),
            ).group_by(group_expr).order_by(group_expr.desc()).limit(limit).all()
            return [{"period": str(r.period), "amount": float(r.amount), "count": r.count} for r in results]
        except Exception:
            return []

    @staticmethod
    def create_invoice(patient_id: int, items: list[dict], notes: str | None = None) -> Any | None:
        from models.invoice import Invoice, InvoiceService
        from models.visit import Visit
        try:
            visit = Visit.query.filter_by(patient_id=patient_id).order_by(Visit.created_at.desc()).first()
            invoice_number = f"INV-{uuid.uuid4().hex[:8].upper()}"
            total = sum(item.get("price", 0) * item.get("quantity", 1) for item in items)
            invoice = Invoice(
                visit_id=visit.id if visit else None,
                total_amount=total,
                invoice_number=invoice_number,
                status="DRAFT",
            )
            db.session.add(invoice)
            db.session.flush()
            for item_data in items:
                item_total = item_data.get("price", 0) * item_data.get("quantity", 1)
                line = InvoiceService(
                    invoice_id=invoice.id,
                    service_code=item_data.get("service_code", f"SVC-{uuid.uuid4().hex[:6].upper()}"),
                    service_name=item_data.get("description", item_data.get("service_name", "")),
                    quantity=item_data.get("quantity", 1),
                    unit_price=item_data.get("price", 0),
                    total_price=item_total,
                    notes=notes or item_data.get("notes"),
                )
                db.session.add(line)
            db.session.commit()
            return invoice
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating invoice: {str(e)}")
            return None

    @staticmethod
    def record_payment(invoice_id: int, amount: float, method: str = "cash", notes: str | None = None) -> bool:
        from models.invoice import Invoice
        from models.visit import Visit
        from services.payment_service import PaymentService
        try:
            invoice = Invoice.query.get(invoice_id)
            if not invoice:
                return False
            visit = db.session.get(Visit, invoice.visit_id) if invoice.visit_id else None
            method_upper = (method or "cash").upper()
            ok, result = PaymentService.create_payment(
                tenant_id=getattr(invoice, "tenant_id", None) or (visit.tenant_id if visit else None),
                operation_type="invoice_payment",
                idempotency_key=None,
                patient_id=visit.patient_id if visit else None,
                visit_id=invoice.visit_id,
                invoice_id=invoice.id,
                method=method_upper,
                amount=amount,
                notes=notes,
            )
            if not ok:
                logging.error(f"Error recording payment: {result}")
                return False
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error recording payment: {str(e)}")
            return False

    @staticmethod
    def get_pending_invoices(limit: int = 50) -> list:
        from models.invoice import Invoice
        return Invoice.query.filter(Invoice.status.in_(["PENDING", "PARTIAL"])).order_by(
            Invoice.created_at.asc()
        ).limit(limit).all()

    @staticmethod
    def get_expenses(category: str | None = None, limit: int = 100) -> dict:
        """Standardized stub — expense model not yet in schema."""
        return {
            "success": True,
            "available": False,
            "expenses": [],
            "message": "Expense tracking is not yet available",
            "category": category,
            "limit": limit,
        }

    @staticmethod
    def record_expense(description: str, amount: float, category: str, recorded_by: int) -> dict:
        """Standardized stub — expense model not yet in schema."""
        logging.info(
            "record_expense stub (desc=%s amount=%s category=%s by=%s)",
            description, amount, category, recorded_by,
        )
        return {
            "success": False,
            "available": False,
            "expense": None,
            "message": "Expense tracking is not yet available",
        }


# Singleton
financial_service = FinancialService()
