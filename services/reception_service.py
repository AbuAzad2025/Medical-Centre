"""
Reception Service - Business logic for reception operations.
Extracted from routes/reception/.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import func, or_, select

from app.extensions import db
from app.shared.enums import VisitState
from utils.db_safety import safe_commit
from utils.tenant_query import TenantContextError, get_tenant_record


class ReceptionService:
    """Centralized reception business logic"""

    @staticmethod
    def get_today_stats() -> dict:
        from models.appointment import Appointment
        from models.visit import Visit

        try:
            today = date.today()
            return {
                'today_visits': db.session.execute(
                    select(func.count())
                    .select_from(Visit)
                    .filter(func.date(Visit.created_at) == today)
                ).scalar(),
                'today_appointments': db.session.execute(
                    select(func.count())
                    .select_from(Appointment)
                    .filter(func.date(Appointment.starts_at) == today)
                ).scalar(),
                'checked_in': db.session.execute(
                    select(func.count())
                    .select_from(Appointment)
                    .filter(
                        func.date(Appointment.starts_at) == today,
                        Appointment.status == 'CHECKED_IN',
                    )
                ).scalar(),
                'waiting': db.session.execute(
                    select(func.count())
                    .select_from(Visit)
                    .filter(Visit.status.in_([VisitState.OPEN.value, VisitState.CHECKED_IN.value]))
                ).scalar(),
            }
        except Exception:
            return {'today_visits': 0, 'today_appointments': 0, 'checked_in': 0, 'waiting': 0}

    @staticmethod
    def register_patient(data: dict) -> Any | None:
        from models.patient import Patient

        try:
            name = data.get('name', '')
            parts = name.split(' ', 1) if name else ('', '')
            patient = Patient(
                first_name=data.get('first_name', parts[0] or name),
                last_name=data.get('last_name', parts[1] if len(parts) > 1 else ''),
                phone=data.get('phone'),
                national_id=data.get('national_id'),
                birth_date=data.get('birth_date') or data.get('date_of_birth'),
                gender=data.get('gender'),
                address=data.get('address'),
            )
            db.session.add(patient)
            if not safe_commit(db.session, error_message='Failed to register patient'):
                return None
            return patient
        except Exception as e:
            logging.exception(f'Error registering patient: {e!s}')
            return None

    @staticmethod
    def search_patients(query: str) -> list:
        from models.patient import Patient

        return (
            db.session.execute(
                select(Patient)
                .filter(
                    or_(
                        Patient.first_name.ilike(f'%{query}%'),
                        Patient.last_name.ilike(f'%{query}%'),
                        Patient.phone.ilike(f'%{query}%'),
                        Patient.national_id.ilike(f'%{query}%'),
                    )
                )
                .order_by(Patient.first_name)
                .limit(20)
            )
            .scalars()
            .all()
        )

    @staticmethod
    def create_visit(
        patient_id: int,
        department_id: int,
        doctor_id: int | None = None,
        visit_type: str = 'OUTPATIENT',
    ) -> Any | None:
        from models.visit import Visit

        try:
            from models.department import Department

            dept = get_tenant_record(Department, department_id)
            visit = Visit(
                patient_id=patient_id,
                department_id=department_id,
                doctor_id=doctor_id,
                visit_type=visit_type,
                status=VisitState.OPEN.value,
                created_at=datetime.now(UTC),
            )
            db.session.add(visit)
            if not safe_commit(db.session, error_message='Failed to create visit'):
                return None
            return visit
        except Exception as e:
            logging.exception(f'Error creating visit: {e!s}')
            return None

    @staticmethod
    def get_queue(department_id: int | None = None) -> list:
        from models.visit import Visit

        query = select(Visit)
        if department_id:
            query = query.filter_by(department_id=department_id)
        return db.session.execute(query.order_by(Visit.created_at.asc())).scalars().all()

    @staticmethod
    def check_in_appointment(appointment_id: int) -> bool:
        from models.appointment import Appointment

        try:
            try:
                apt = get_tenant_record(Appointment, appointment_id)
            except TenantContextError:
                return False
            apt.status = 'CHECKED_IN'
            return safe_commit(db.session, error_message='Failed to check in appointment')
        except Exception:
            return False

    @staticmethod
    def get_patient(patient_id: int):
        from models.patient import Patient

        return get_tenant_record(Patient, patient_id)

    @staticmethod
    def get_visit(visit_id: int):
        from models.visit import Visit

        return get_tenant_record(Visit, visit_id)

    @staticmethod
    def get_upcoming_appointments(department_id: int | None = None, limit: int = 20) -> list:
        from datetime import datetime

        from models.appointment import Appointment

        now = datetime.now(UTC)
        query = select(Appointment).filter(Appointment.starts_at >= now)
        if department_id:
            query = query.filter_by(department_id=department_id)
        return (
            db.session.execute(query.order_by(Appointment.starts_at.asc()).limit(limit))
            .scalars()
            .all()
        )


# Singleton
reception_service = ReceptionService()
