"""
Core Query Service - Consolidates common database query patterns used across routes.
Single source of truth for common queries to avoid duplication in routes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import desc, func, or_, select

from app.extensions import db
from app.shared.enums import VisitState
from utils.tenant_query import get_tenant_record, tenant_filter

if TYPE_CHECKING:
    from models.appointment import Appointment
    from models.department import Department
    from models.emergency import EmergencyCase
    from models.invoice import Invoice
    from models.lab_request import LabRequest, LabResult
    from models.medication import Medication, Prescription
    from models.patient import Patient
    from models.payment import Payment
    from models.radiology_request import RadiologyRequest
    from models.radiology_result import RadiologyResult
    from models.user import User
    from models.visit import Visit


class CoreQueryService:
    """Centralized common queries - routes should use this instead of direct Model.query"""

    # ==================== PATIENT QUERIES ====================
    @staticmethod
    def get_patient_by_id(patient_id: int) -> Patient | None:
        from models.patient import Patient

        return get_tenant_record(Patient, patient_id)

    @staticmethod
    def get_patient_by_code(code: str) -> Patient | None:
        from models.patient import Patient

        return (
            db.session.execute(
                tenant_filter(Patient).filter_by(code=code)
            )
            .scalars()
            .first()
        )

    @staticmethod
    def search_patients(
        query: str = '',
        department_id: int | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Patient]:
        from models.patient import Patient

        q = tenant_filter(Patient)
        if query:
            q = q.filter(
                or_(
                    Patient.name.ilike(f'%{query}%'),
                    Patient.code.ilike(f'%{query}%'),
                    Patient.phone.ilike(f'%{query}%'),
                )
            )
        if department_id:
            q = q.filter_by(department_id=department_id)
        return q.order_by(desc(Patient.created_at)).offset(offset).limit(limit).all()

    @staticmethod
    def count_patients(query: str = '', department_id: int | None = None) -> int:
        from models.patient import Patient

        q = tenant_filter(Patient)
        if query:
            q = q.filter(
                or_(
                    Patient.name.ilike(f'%{query}%'),
                    Patient.code.ilike(f'%{query}%'),
                    Patient.phone.ilike(f'%{query}%'),
                )
            )
        if department_id:
            q = q.filter_by(department_id=department_id)
        return q.count()

    # ==================== VISIT QUERIES ====================
    @staticmethod
    def get_visit_by_id(visit_id: int) -> Visit | None:
        from models.visit import Visit

        return get_tenant_record(Visit, visit_id)

    @staticmethod
    def get_visits_by_patient(patient_id: int, limit: int = 50) -> list[Visit]:
        from models.visit import Visit

        return (
            db.session.execute(
                select(Visit)
                .filter_by(patient_id=patient_id)
                .order_by(desc(Visit.created_at))
                .limit(limit)
            )
            .scalars()
            .all()
        )

    @staticmethod
    def get_open_visits(department_id: int | None = None) -> list[Visit]:
        from models.visit import Visit

        q = tenant_filter(Visit)
        if department_id:
            q = q.filter_by(department_id=department_id)
        return q.order_by(Visit.created_at).all()

    @staticmethod
    def get_visits_for_queue(
        department_id: int | None = None,
        status_filter: list[str] | None = None,
    ) -> list[Visit]:
        from models.visit import Visit

        q = tenant_filter(Visit)
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
        from datetime import date

        from models.visit import Visit

        today = date.today()
        return db.session.execute(
            select(func.count()).select_from(Visit).filter(func.date(Visit.created_at) == today)
        ).scalar()

    # ==================== USER/STAFF QUERIES ====================
    @staticmethod
    def get_user_by_id(user_id: int) -> User | None:
        from models.user import User

        return get_tenant_record(User, user_id)

    @staticmethod
    def get_doctors(department_id: int | None = None) -> list[User]:
        from models.user import User

        q = tenant_filter(User).filter_by(role='doctor')
        if department_id:
            q = q.filter_by(department_id=department_id)
        return q.order_by(User.full_name).all()

    @staticmethod
    def get_nurses(department_id: int | None = None) -> list[User]:
        from models.user import User

        q = tenant_filter(User).filter_by(role='nurse')
        if department_id:
            q = q.filter_by(department_id=department_id)
        return q.order_by(User.full_name).all()

    @staticmethod
    def get_staff_by_role(role: str, department_id: int | None = None) -> list[User]:
        from models.user import User

        q = tenant_filter(User).filter_by(role=role)
        if department_id:
            q = q.filter_by(department_id=department_id)
        return q.order_by(User.full_name).all()

    # ==================== DEPARTMENT QUERIES ====================
    @staticmethod
    def get_department_by_id(dept_id: int) -> Department | None:
        from models.department import Department

        return get_tenant_record(Department, dept_id)

    @staticmethod
    def get_all_departments(active_only: bool = True) -> list[Department]:
        from models.department import Department

        q = tenant_filter(Department)
        if active_only:
            q = q.filter_by(is_active=True)
        return q.order_by(Department.name).all()

    # ==================== PAYMENT/INVOICE QUERIES ====================
    @staticmethod
    def get_payments_by_patient(patient_id: int) -> list[Payment]:
        from models.payment import Payment

        return (
            db.session.execute(
                select(Payment)
                .filter_by(patient_id=patient_id)
                .order_by(desc(Payment.payment_date))
            )
            .scalars()
            .all()
        )

    @staticmethod
    def get_invoices_by_patient(patient_id: int) -> list[Invoice]:
        from models.invoice import Invoice

        return (
            db.session.execute(
                select(Invoice).filter_by(patient_id=patient_id).order_by(desc(Invoice.created_at))
            )
            .scalars()
            .all()
        )

    @staticmethod
    def get_revenue_today() -> float:
        from datetime import date

        from flask import g

        from models.payment import Payment

        today = date.today()
        tenant_id = getattr(g, 'tenant_id', None)
        q = select(func.sum(Payment.amount)).filter(func.date(Payment.payment_date) == today)
        if tenant_id is not None and hasattr(Payment, 'tenant_id'):
            q = q.filter(Payment.tenant_id == tenant_id)
        total = db.session.execute(q).scalar()
        return float(total or 0)

    @staticmethod
    def get_revenue_this_month() -> float:
        from datetime import date

        from flask import g

        from models.payment import Payment

        first_day = date.today().replace(day=1)
        tenant_id = getattr(g, 'tenant_id', None)
        q = select(func.sum(Payment.amount)).filter(Payment.payment_date >= first_day)
        if tenant_id is not None and hasattr(Payment, 'tenant_id'):
            q = q.filter(Payment.tenant_id == tenant_id)
        total = db.session.execute(q).scalar()
        return float(total or 0)

    # ==================== APPOINTMENT QUERIES ====================
    @staticmethod
    def get_appointments_for_doctor(
        doctor_id: int, date_from=None, date_to=None
    ) -> list[Appointment]:
        from models.appointment import Appointment

        q = tenant_filter(Appointment).filter_by(doctor_id=doctor_id)
        if date_from:
            q = q.filter(Appointment.appointment_date >= date_from)
        if date_to:
            q = q.filter(Appointment.appointment_date <= date_to)
        return q.order_by(Appointment.appointment_time).all()

    @staticmethod
    def get_appointments_today() -> list[Appointment]:
        from datetime import date

        from models.appointment import Appointment

        today = date.today()
        return (
            db.session.execute(
                select(Appointment)
                .filter(func.date(Appointment.appointment_date) == today)
                .order_by(Appointment.appointment_time)
            )
            .scalars()
            .all()
        )

    # ==================== LAB QUERIES ====================
    @staticmethod
    def get_lab_requests_for_worklist(status_filter: list[str] | None = None) -> list[LabRequest]:
        from models.lab_request import LabRequest

        q = tenant_filter(LabRequest)
        if status_filter:
            q = q.filter(LabRequest.status.in_(status_filter))
        return q.order_by(LabRequest.created_at).all()

    @staticmethod
    def get_lab_results_ready(patient_id: int | None = None) -> list[LabResult]:
        from models.lab_request import LabResult

        q = tenant_filter(LabResult).join(LabRequest)
        if patient_id:
            q = q.filter(LabRequest.patient_id == patient_id)
        return q.order_by(desc(LabResult.completed_at)).all()

    # ==================== RADIOLOGY QUERIES ====================
    @staticmethod
    def get_radiology_requests_for_worklist(
        status_filter: list[str] | None = None,
    ) -> list[RadiologyRequest]:
        from models.radiology_request import RadiologyRequest

        q = tenant_filter(RadiologyRequest)
        if status_filter:
            q = q.filter(RadiologyRequest.status.in_(status_filter))
        return q.order_by(RadiologyRequest.created_at).all()

    @staticmethod
    def get_radiology_results_ready(patient_id: int | None = None) -> list[RadiologyResult]:
        from models.radiology_result import RadiologyResult

        q = tenant_filter(RadiologyResult).join(RadiologyRequest)
        if patient_id:
            q = q.filter(RadiologyRequest.patient_id == patient_id)
        return q.order_by(desc(RadiologyResult.completed_at)).all()

    # ==================== MEDICATION QUERIES ====================
    @staticmethod
    def get_active_medications() -> list[Medication]:
        from models.medication import Medication

        return (
            db.session.execute(
                tenant_filter(Medication).filter_by(is_active=True).order_by(Medication.name)
            )
            .scalars()
            .all()
        )

    @staticmethod
    def get_prescriptions_by_patient(patient_id: int) -> list[Prescription]:
        from models.medication import Prescription

        return (
            db.session.execute(
                tenant_filter(Prescription)
                .filter_by(patient_id=patient_id)
                .order_by(desc(Prescription.created_at))
            )
            .scalars()
            .all()
        )

    # ==================== EMERGENCY QUERIES ====================
    @staticmethod
    def get_active_emergency_cases() -> list[EmergencyCase]:
        from models.emergency import EmergencyCase

        return (
            db.session.execute(
                tenant_filter(EmergencyCase)
                .filter(EmergencyCase.status.in_(['TRIAGE', 'IN_PROGRESS', 'OBSERVATION']))
                .order_by(EmergencyCase.created_at)
            )
            .scalars()
            .all()
        )

    @staticmethod
    def get_emergency_case_by_id(case_id: int) -> EmergencyCase | None:
        from models.emergency import EmergencyCase

        return get_tenant_record(EmergencyCase, case_id)

    # ==================== DASHBOARD STATS ====================
    @staticmethod
    def get_basic_dashboard_stats() -> dict:
        """Common stats used by multiple dashboards"""
        from datetime import date

        from flask import g

        from models.patient import Patient
        from models.user import User
        from models.visit import Visit

        today = date.today()
        tenant_id = getattr(g, 'tenant_id', None)

        def _count_with_tenant(model):
            q = select(func.count())
            if tenant_id is not None and hasattr(model, 'tenant_id'):
                q = q.filter(model.tenant_id == tenant_id)
            return db.session.execute(q).scalar()

        def _count_with_tenant_and_date_filter(model, date_filter):
            q = select(func.count())
            if tenant_id is not None and hasattr(model, 'tenant_id'):
                q = q.filter(model.tenant_id == tenant_id)
            if date_filter is not None:
                q = q.filter(date_filter)
            return db.session.execute(q).scalar()

        return {
            'total_patients': _count_with_tenant(Patient),
            'new_patients_today': _count_with_tenant_and_date_filter(
                Patient, func.date(Patient.created_at) == today
            ),
            'total_visits': _count_with_tenant(Visit),
            'visits_today': _count_with_tenant_and_date_filter(
                Visit, func.date(Visit.created_at) == today
            ),
            'total_users': _count_with_tenant(User),
            'active_users': _count_with_tenant_and_date_filter(
                User, User.is_active.is_(True)
            ),
            'revenue_today': CoreQueryService.get_revenue_today(),
            'revenue_month': CoreQueryService.get_revenue_this_month(),
        }


# Singleton instance
core_queries = CoreQueryService()
