"""
AppointmentService — booking, reschedule, no-show, convert-to-visit
"""
from datetime import datetime, timezone, timedelta
from typing import Optional
from app.extensions import db
from app.shared.enums import AppointmentWorkflowStatus as AppointmentStatus


class AppointmentService:
    VALID_TRANSITIONS = {
        AppointmentStatus.SCHEDULED: {AppointmentStatus.CONFIRMED, AppointmentStatus.CANCELLED},
        AppointmentStatus.CONFIRMED: {AppointmentStatus.CHECKED_IN, AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW},
        AppointmentStatus.CHECKED_IN: {AppointmentStatus.IN_PROGRESS, AppointmentStatus.CANCELLED},
        AppointmentStatus.IN_PROGRESS: {AppointmentStatus.DONE},
        AppointmentStatus.DONE: set(),
        AppointmentStatus.CANCELLED: set(),
        AppointmentStatus.NO_SHOW: set(),
    }

    @staticmethod
    def can_transition(current: str, target: str) -> bool:
        return target in AppointmentService.VALID_TRANSITIONS.get(AppointmentStatus(current), set())

    @staticmethod
    def transition(appointment, new_status: str, performed_by: Optional[int] = None) -> None:
        current = appointment.status or AppointmentStatus.SCHEDULED
        if not AppointmentService.can_transition(current, new_status):
            raise ValueError(f"Invalid appointment transition from {current} to {new_status}")
        appointment.status = new_status
        appointment.updated_at = datetime.now(timezone.utc)
        db.session.add(appointment)

    @staticmethod
    def check_double_booking(doctor_id: int, start_time: datetime, end_time: datetime,
                              exclude_id: Optional[int] = None) -> bool:
        from models.appointment import Appointment
        q = Appointment.query.filter(
            Appointment.doctor_id == doctor_id,
            Appointment.status.notin_([AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW]),
            Appointment.starts_at < end_time,
            Appointment.ends_at > start_time,
        )
        if exclude_id:
            q = q.filter(Appointment.id != exclude_id)
        return q.first() is not None

    @staticmethod
    def convert_to_visit(appointment, created_by: Optional[int] = None) -> object:
        from models.visit import Visit
        if appointment.status not in (AppointmentStatus.CHECKED_IN, AppointmentStatus.IN_PROGRESS, AppointmentStatus.DONE):
            raise ValueError("Appointment must be checked-in or in-progress to convert to visit")

        visit = Visit(
            patient_id=appointment.patient_id,
            doctor_id=appointment.doctor_id,
            department_id=appointment.department_id,
            status="registered",
            appointment_id=appointment.id,
            created_by=created_by,
        )
        db.session.add(visit)
        appointment.status = AppointmentStatus.DONE
        db.session.add(appointment)
        return visit
