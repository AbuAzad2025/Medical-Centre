"""
Reception Service - Business logic for reception operations.
Extracted from routes/reception/.
"""
from __future__ import annotations

import logging
from datetime import datetime, date, timezone
from typing import Any

from app_factory import db
from app.shared.enums import VisitState
from sqlalchemy import and_, or_, func


class ReceptionService:
    """Centralized reception business logic"""

    @staticmethod
    def get_today_stats() -> dict:
        from models.visit import Visit
        from models.appointment import Appointment
        try:
            today = date.today()
            return {
                "today_visits": Visit.query.filter(func.date(Visit.created_at) == today).count(),
                "today_appointments": Appointment.query.filter(func.date(Appointment.starts_at) == today).count(),
                "checked_in": Appointment.query.filter(
                    func.date(Appointment.starts_at) == today,
                    Appointment.status == "CHECKED_IN",
                ).count(),
                "waiting": Visit.query.filter(Visit.status.in_([VisitState.OPEN.value, VisitState.CHECKED_IN.value])).count(),
            }
        except Exception:
            return {"today_visits": 0, "today_appointments": 0, "checked_in": 0, "waiting": 0}

    @staticmethod
    def register_patient(data: dict) -> Any | None:
        from models.patient import Patient
        try:
            name = data.get("name", "")
            parts = name.split(" ", 1) if name else ("", "")
            patient = Patient(
                first_name=data.get("first_name", parts[0] or name),
                last_name=data.get("last_name", parts[1] if len(parts) > 1 else ""),
                phone=data.get("phone"),
                national_id=data.get("national_id"),
                birth_date=data.get("birth_date") or data.get("date_of_birth"),
                gender=data.get("gender"),
                address=data.get("address"),
            )
            db.session.add(patient)
            db.session.commit()
            return patient
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error registering patient: {str(e)}")
            return None

    @staticmethod
    def search_patients(query: str) -> list:
        from models.patient import Patient
        return Patient.query.filter(
            or_(
                Patient.first_name.ilike(f"%{query}%"),
                Patient.last_name.ilike(f"%{query}%"),
                Patient.phone.ilike(f"%{query}%"),
                Patient.national_id.ilike(f"%{query}%"),
            )
        ).order_by(Patient.first_name).limit(20).all()

    @staticmethod
    def create_visit(patient_id: int, department_id: int, doctor_id: int | None = None, visit_type: str = "OUTPATIENT") -> Any | None:
        from models.visit import Visit
        try:
            from models.department import Department
            dept = Department.query.get(department_id)
            visit = Visit(
                patient_id=patient_id,
                department_id=department_id,
                doctor_id=doctor_id,
                visit_type=visit_type,
                status=VisitState.OPEN.value,
                created_at=datetime.now(timezone.utc),
            )
            db.session.add(visit)
            db.session.commit()
            return visit
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating visit: {str(e)}")
            return None

    @staticmethod
    def get_queue(department_id: int | None = None) -> list:
        from models.visit import Visit
        from models.patient import Patient
        query = Visit.query.filter(Visit.status.in_([VisitState.OPEN.value, VisitState.CHECKED_IN.value]))
        if department_id:
            query = query.filter_by(department_id=department_id)
        return query.order_by(Visit.created_at.asc()).all()

    @staticmethod
    def check_in_appointment(appointment_id: int) -> bool:
        from models.appointment import Appointment
        try:
            apt = Appointment.query.get(appointment_id)
            if not apt:
                return False
            apt.status = "CHECKED_IN"
            db.session.commit()
            return True
        except Exception:
            db.session.rollback()
            return False

    @staticmethod
    def get_patient(patient_id: int):
        from models.patient import Patient
        return Patient.query.get(patient_id)

    @staticmethod
    def get_visit(visit_id: int):
        from models.visit import Visit
        return Visit.query.get(visit_id)

    @staticmethod
    def get_upcoming_appointments(department_id: int | None = None, limit: int = 20) -> list:
        from models.appointment import Appointment
        query = Appointment.query.filter(
            func.date(Appointment.starts_at) >= date.today(),
            Appointment.status.in_(["SCHEDULED", "CONFIRMED"]),
        )
        if department_id:
            query = query.filter_by(department_id=department_id)
        return query.order_by(Appointment.starts_at.asc()).limit(limit).all()


# Singleton
reception_service = ReceptionService()
