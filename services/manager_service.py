"""
Manager Service - Business logic for manager operations.
Extracted from routes/manager/.
"""
from __future__ import annotations

import logging
from datetime import datetime, date, timezone
from typing import Any

from app_factory import db
from sqlalchemy import func, and_, or_


class ManagerService:
    """Centralized manager business logic"""

    @staticmethod
    def get_organization_stats() -> dict:
        from models.user import User
        from models.patient import Patient
        from models.visit import Visit
        from models.department import Department
        try:
            return {
                "total_patients": Patient.query.count(),
                "total_staff": User.query.filter(User.role != "patient").count(),
                "total_visits": Visit.query.count(),
                "total_departments": Department.query.count(),
                "today_visits": Visit.query.filter(func.date(Visit.created_at) == date.today()).count(),
                "active_visits": Visit.query.filter(Visit.status.in_(["WAITING", "INPATIENT", "OBSERVATION"])).count(),
            }
        except Exception:
            return {}

    @staticmethod
    def get_financial_summary(period: str = "monthly") -> dict:
        from models.invoice import Invoice, Payment
        try:
            from models.invoice import Expense
        except ImportError:
            Expense = None
        try:
            total_billed = db.session.query(func.coalesce(func.sum(Invoice.total_amount), 0)).scalar()
            total_collected = db.session.query(func.coalesce(func.sum(Payment.amount), 0)).scalar()
            total_expenses = db.session.query(func.coalesce(func.sum(Expense.amount), 0)).scalar() if Expense is not None else 0
            return {
                "total_billed": float(total_billed),
                "total_collected": float(total_collected),
                "total_expenses": float(total_expenses),
                "net_revenue": float(total_collected) - float(total_expenses),
            }
        except Exception:
            return {}

    @staticmethod
    def get_staff_stats() -> dict:
        from models.user import User
        try:
            total = User.query.filter(User.role != "patient").count()
            active = User.query.filter(User.role != "patient", User.is_active == True).count()
            return {"total": total, "active": active}
        except Exception:
            return {"total": 0, "active": 0}

    @staticmethod
    def get_recent_activities(limit: int = 20) -> list:
        try:
            from models.audit_trail import AuditTrail
            return AuditTrail.query.order_by(AuditTrail.created_at.desc()).limit(limit).all()
        except Exception:
            return []

    @staticmethod
    def get_department_performance(department_id: int | None = None) -> list:
        from models.visit import Visit
        from models.department import Department
        from models.patient import Patient
        try:
            query = db.session.query(
                Department.name,
                func.count(Visit.id).label("visit_count"),
            ).join(Visit, Visit.department_id == Department.id)
            if department_id:
                query = query.filter(Department.id == department_id)
            results = query.group_by(Department.name).order_by(func.count(Visit.id).desc()).all()
            return [{"department": r.name, "visits": r.visit_count} for r in results]
        except Exception:
            return []

    @staticmethod
    def get_satisfaction_stats() -> dict:
        try:
            from models.feedback import PatientFeedback
            avg = db.session.query(func.avg(PatientFeedback.rating)).scalar()
            count = PatientFeedback.query.count()
            return {"average_rating": float(avg) if avg else 0, "total_responses": count}
        except Exception:
            return {"average_rating": 0, "total_responses": 0}

    @staticmethod
    def approve_request(request_type: str, request_id: int, approved_by: int) -> bool:
        try:
            if request_type == "leave":
                from models.staff import LeaveRequest
                obj = LeaveRequest.query.get(request_id)
            elif request_type == "expense":
                from models.invoice import Expense
                obj = Expense.query.get(request_id)
            else:
                return False
            if not obj:
                return False
            obj.status = "APPROVED"
            obj.approved_by = approved_by
            db.session.commit()
            return True
        except Exception:
            db.session.rollback()
            return False


# Singleton
manager_service = ManagerService()
