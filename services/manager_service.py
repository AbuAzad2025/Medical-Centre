"""
Manager Service - Business logic for manager operations.
Extracted from routes/manager/.
"""
from __future__ import annotations

import logging
from datetime import datetime, date, timezone
from typing import Any

from app.extensions import db
from utils.db_safety import safe_commit
from sqlalchemy import func, and_, or_, select

from utils.tenant_query import get_tenant_record, TenantContextError


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
                "total_patients": db.session.execute(select(func.count()).select_from(Patient)).scalar(),
                "total_staff": db.session.execute(select(func.count()).select_from(User).filter(User.role != "patient")).scalar(),
                "total_visits": db.session.execute(select(func.count()).select_from(Visit)).scalar(),
                "total_departments": db.session.execute(select(func.count()).select_from(Department)).scalar(),
                "today_visits": db.session.execute(select(func.count()).select_from(Visit).filter(func.date(Visit.created_at) == date.today())).scalar(),
                "active_visits": db.session.execute(select(func.count()).select_from(Visit).filter(Visit.status.in_(["WAITING", "INPATIENT", "OBSERVATION"]))).scalar(),
            }
        except Exception:
            return {}

    @staticmethod
    def get_financial_summary(period: str = "monthly") -> dict:
        from models.invoice import Invoice, Payment
        from models.expense import Expense
        try:
            total_billed = db.session.execute(select(func.coalesce(func.sum(Invoice.total_amount), 0))).scalar()
            total_collected = db.session.execute(select(func.coalesce(func.sum(Payment.amount), 0))).scalar()
            total_expenses = db.session.execute(select(func.coalesce(func.sum(Expense.amount), 0))).scalar()
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
            total = db.session.execute(select(func.count()).select_from(User).filter(User.role != "patient")).scalar()
            active = db.session.execute(select(func.count()).select_from(User).filter(User.role != "patient", User.is_active == True)).scalar()
            return {"total": total, "active": active}
        except Exception:
            return {"total": 0, "active": 0}

    @staticmethod
    def get_recent_activities(limit: int = 20) -> list:
        try:
            from models.audit_trail import AuditTrail
            return db.session.execute(select(AuditTrail).order_by(AuditTrail.created_at.desc()).limit(limit)).scalars().all()
        except Exception:
            return []

    @staticmethod
    def get_department_performance(department_id: int | None = None) -> list:
        from models.visit import Visit
        from models.department import Department
        from models.patient import Patient
        try:
            query = select(
                Department.name,
                func.count(Visit.id).label("visit_count"),
            ).join(Visit, Visit.department_id == Department.id)
            if department_id:
                query = query.filter(Department.id == department_id)
            results = db.session.execute(query.group_by(Department.name).order_by(func.count(Visit.id).desc())).scalars().all()
            return [{"department": r.name, "visits": r.visit_count} for r in results]
        except Exception:
            return []

    @staticmethod
    def get_satisfaction_stats() -> dict:
        try:
            from models.feedback import PatientFeedback
            avg = db.session.execute(select(func.avg(PatientFeedback.rating))).scalar()
            count = db.session.execute(select(func.count()).select_from(PatientFeedback)).scalar()
            return {"average_rating": float(avg) if avg else 0, "total_responses": count}
        except Exception:
            return {"average_rating": 0, "total_responses": 0}

    @staticmethod
    def approve_request(request_type: str, request_id: int, approved_by: int) -> bool:
        try:
            if request_type == "leave":
                from models.staff import LeaveRequest
                try:
                    obj = get_tenant_record(LeaveRequest, request_id)
                except TenantContextError:
                    return False
            elif request_type == "expense":
                from models.expense import Expense
                try:
                    obj = get_tenant_record(Expense, request_id)
                except TenantContextError:
                    return False
            else:
                return False
            obj.status = "APPROVED"
            obj.approved_by = approved_by
            return safe_commit(db.session, error_message="Failed to approve request")
        except Exception:
            return False


# Singleton
manager_service = ManagerService()
