"""
Core Query Service - Consolidates common database query patterns used across routes.
Single source of truth for common queries to avoid duplication in routes.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, and_, or_, desc
from sqlalchemy.orm import Query

from app.shared.enums import VisitState
from app_factory import db

if TYPE_CHECKING:
    from models.patient import Patient
    from models.visit import Visit
    from models.user import User
    from models.department import Department
    from models.payment import Payment
    from models.invoice import Invoice
    from models.appointment import Appointment
    from models.lab_request import LabRequest, LabResult
    from models.radiology_request import RadiologyRequest
    from models.radiology_result import RadiologyResult
    from models.medication import Medication, Prescription
    from models.emergency import EmergencyCase


class CoreQueryService:
    """Centralized common queries - routes should use this instead of direct Model.query"""

    # ==================== PATIENT QUERIES ====================
    @staticmethod
    def get_patient_by_id(patient_id: int) -> Patient | None:
        from models.patient import Patient
        return Patient.query.get(patient_id)

    @staticmethod
    def get_patient_by_code(code: str) -> Patient | None:
        from models.patient import Patient
        return Patient.query.filter_by(code=code).first()

    @staticmethod
    def search_patients(
        query: str = "",
        department_id: int | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Patient]:
        from models.patient import Patient
        q = Patient.query
        if query:
            q = q.filter(
                or_(
                    Patient.name.ilike(f"%{query}%"),
                    Patient.code.ilike(f"%{query}%"),
                    Patient.phone.ilike(f"%{query}%"),
                )
            )
        if department_id:
            q = q.filter_by(department_id=department_id)
        return q.order_by(desc(Patient.created_at)).offset(offset).limit(limit).all()

    @staticmethod
    def count_patients(query: str = "", department_id: int | None = None) -> int:
        from models.patient import Patient
        q = Patient.query
        if query:
            q = q.filter(
                or_(
                    Patient.name.ilike(f"%{query}%"),
                    Patient.code.ilike(f"%{query}%"),
                    Patient.phone.ilike(f"%{query}%"),
                )
            )
        if department_id:
            q = q.filter_by(department_id=department_id)
        return q.count()

    # ==================== VISIT QUERIES ====================
    @staticmethod
    def get_visit_by_id(visit_id: int) -> Visit | None:
        from models.visit import Visit
        return Visit.query.get(visit_id)

    @staticmethod
    def get_visits_by_patient(patient_id: int, limit: int = 50) -> list[Visit]:
        from models.visit import Visit
        return (
            Visit.query.filter_by(patient_id=patient_id)
            .order_by(desc(Visit.created_at))
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_open_visits(department_id: int | None = None) -> list[Visit]:
        from models.visit import Visit
        q = Visit.query.filter(Visit.status.in_([VisitState.OPEN, VisitState.IN_PROGRESS]))
        if department_id:
            q = q.filter_by(department_id=department_id)
        return q.order_by(Visit.created_at).all()

    @staticmethod
    def get_visits_for_queue(
        department_id: int | None = None,
        status_filter: list[str] | None = None,
    ) -> list[Visit]:
        from models.visit import Visit
        q = Visit.query
        if status_filter:
            q = q.filter(Visit.status.in_(status_filter))
        elif department_id:
            q = q.filter(
                Visit.department_id == department_id,
                Visit.status.in_([VisitState.OPEN, VisitState.IN_PROGRESS]),
            )
        return q.order_by(Visit.queue_number).all()

    @staticmethod
    def count_visits_today() -> int:
        from models.visit import Visit
        from datetime import date, datetime
        today = date.today()
        return Visit.query.filter(
            func.date(Visit.created_at) == today
        ).count()

    # ==================== USER/STAFF QUERIES ====================
    @staticmethod
    def get_user_by_id(user_id: int) -> User | None:
        from models.user import User
        return User.query.get(user_id)

    @staticmethod
    def get_doctors(department_id: int | None = None) -> list[User]:
        from models.user import User
        q = User.query.filter_by(role="doctor", is_active=True)
        if department_id:
            q = q.filter_by(department_id=department_id)
        return q.order_by(User.full_name).all()

    @staticmethod
    def get_nurses(department_id: int | None = None) -> list[User]:
        from models.user import User
        q = User.query.filter_by(role="nurse", is_active=True)
        if department_id:
            q = q.filter_by(department_id=department_id)
        return q.order_by(User.full_name).all()

    @staticmethod
    def get_staff_by_role(role: str, department_id: int | None = None) -> list[User]:
        from models.user import User
        q = User.query.filter_by(role=role, is_active=True)
        if department_id:
            q = q.filter_by(department_id=department_id)
        return q.order_by(User.full_name).all()

    # ==================== DEPARTMENT QUERIES ====================
    @staticmethod
    def get_department_by_id(dept_id: int) -> Department | None:
        from models.department import Department
        return Department.query.get(dept_id)

    @staticmethod
    def get_all_departments(active_only: bool = True) -> list[Department]:
        from models.department import Department
        q = Department.query
        if active_only:
            q = q.filter_by(is_active=True)
        return q.order_by(Department.name).all()

    # ==================== PAYMENT/INVOICE QUERIES ====================
    @staticmethod
    def get_payments_by_patient(patient_id: int) -> list[Payment]:
        from models.payment import Payment
        return Payment.query.filter_by(patient_id=patient_id).order_by(desc(Payment.payment_date)).all()

    @staticmethod
    def get_invoices_by_patient(patient_id: int) -> list[Invoice]:
        from models.invoice import Invoice
        return Invoice.query.filter_by(patient_id=patient_id).order_by(desc(Invoice.created_at)).all()

    @staticmethod
    def get_revenue_today() -> float:
        from models.payment import Payment
        from datetime import date
        today = date.today()
        total = db.session.query(func.sum(Payment.amount)).filter(
            func.date(Payment.payment_date) == today
        ).scalar()
        return float(total or 0)

    @staticmethod
    def get_revenue_this_month() -> float:
        from models.payment import Payment
        from datetime import date
        first_day = date.today().replace(day=1)
        total = db.session.query(func.sum(Payment.amount)).filter(
            Payment.payment_date >= first_day
        ).scalar()
        return float(total or 0)

    # ==================== APPOINTMENT QUERIES ====================
    @staticmethod
    def get_appointments_for_doctor(doctor_id: int, date_from=None, date_to=None) -> list[Appointment]:
        from models.appointment import Appointment
        q = Appointment.query.filter_by(doctor_id=doctor_id)
        if date_from:
            q = q.filter(Appointment.appointment_date >= date_from)
        if date_to:
            q = q.filter(Appointment.appointment_date <= date_to)
        return q.order_by(Appointment.appointment_time).all()

    @staticmethod
    def get_appointments_today() -> list[Appointment]:
        from models.appointment import Appointment
        from datetime import date
        today = date.today()
        return Appointment.query.filter(
            func.date(Appointment.appointment_date) == today
        ).order_by(Appointment.appointment_time).all()

    # ==================== LAB QUERIES ====================
    @staticmethod
    def get_lab_requests_for_worklist(status_filter: list[str] | None = None) -> list[LabRequest]:
        from models.lab_request import LabRequest
        q = LabRequest.query
        if status_filter:
            q = q.filter(LabRequest.status.in_(status_filter))
        return q.order_by(LabRequest.created_at).all()

    @staticmethod
    def get_lab_results_ready(patient_id: int | None = None) -> list[LabResult]:
        from models.lab_request import LabResult
        q = LabResult.query.filter_by(status="COMPLETED")
        if patient_id:
            q = q.join(LabRequest).filter(LabRequest.patient_id == patient_id)
        return q.order_by(desc(LabResult.completed_at)).all()

    # ==================== RADIOLOGY QUERIES ====================
    @staticmethod
    def get_radiology_requests_for_worklist(status_filter: list[str] | None = None) -> list[RadiologyRequest]:
        from models.radiology_request import RadiologyRequest
        q = RadiologyRequest.query
        if status_filter:
            q = q.filter(RadiologyRequest.status.in_(status_filter))
        return q.order_by(RadiologyRequest.created_at).all()

    @staticmethod
    def get_radiology_results_ready(patient_id: int | None = None) -> list[RadiologyResult]:
        from models.radiology_result import RadiologyResult
        q = RadiologyResult.query.filter_by(status="COMPLETED")
        if patient_id:
            q = q.join(RadiologyRequest).filter(RadiologyRequest.patient_id == patient_id)
        return q.order_by(desc(RadiologyResult.completed_at)).all()

    # ==================== MEDICATION QUERIES ====================
    @staticmethod
    def get_active_medications() -> list[Medication]:
        from models.medication import Medication
        return Medication.query.filter_by(is_active=True).order_by(Medication.name).all()

    @staticmethod
    def get_prescriptions_by_patient(patient_id: int) -> list[Prescription]:
        from models.medication import Prescription
        return Prescription.query.filter_by(patient_id=patient_id).order_by(desc(Prescription.created_at)).all()

    # ==================== EMERGENCY QUERIES ====================
    @staticmethod
    def get_active_emergency_cases() -> list[EmergencyCase]:
        from models.emergency import EmergencyCase
        return EmergencyCase.query.filter(
            EmergencyCase.status.in_(["TRIAGE", "IN_PROGRESS", "OBSERVATION"])
        ).order_by(EmergencyCase.created_at).all()

    @staticmethod
    def get_emergency_case_by_id(case_id: int) -> EmergencyCase | None:
        from models.emergency import EmergencyCase
        return EmergencyCase.query.get(case_id)

    # ==================== DASHBOARD STATS ====================
    @staticmethod
    def get_basic_dashboard_stats() -> dict:
        """Common stats used by multiple dashboards"""
        from models.patient import Patient
        from models.visit import Visit
        from models.user import User
        from models.payment import Payment
        from datetime import date
        today = date.today()
        return {
            "total_patients": Patient.query.count(),
            "new_patients_today": Patient.query.filter(func.date(Patient.created_at) == today).count(),
            "total_visits": Visit.query.count(),
            "visits_today": Visit.query.filter(func.date(Visit.created_at) == today).count(),
            "total_users": User.query.count(),
            "active_users": User.query.filter_by(is_active=True).count(),
            "revenue_today": CoreQueryService.get_revenue_today(),
            "revenue_month": CoreQueryService.get_revenue_this_month(),
        }


# Singleton instance
core_queries = CoreQueryService()