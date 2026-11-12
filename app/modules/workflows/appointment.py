"""
AppointmentService — booking, reschedule, no-show, convert-to-visit
"""

from datetime import UTC, datetime

from sqlalchemy import or_, select

from app.extensions import db
from app.shared.enums import AppointmentWorkflowStatus as AppointmentStatus


class AppointmentService:
    VALID_TRANSITIONS = {
        AppointmentStatus.SCHEDULED: {AppointmentStatus.CONFIRMED, AppointmentStatus.CANCELLED},
        AppointmentStatus.CONFIRMED: {
            AppointmentStatus.CHECKED_IN,
            AppointmentStatus.CANCELLED,
            AppointmentStatus.NO_SHOW,
        },
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
    def transition(appointment, new_status: str, performed_by: int | None = None) -> None:
        current = appointment.status or AppointmentStatus.SCHEDULED
        if not AppointmentService.can_transition(current, new_status):
            raise ValueError(f'Invalid appointment transition from {current} to {new_status}')
        appointment.status = new_status
        appointment.updated_at = datetime.now(UTC)
        db.session.add(appointment)

    @staticmethod
    def check_double_booking(
        doctor_id: int, start_time: datetime, end_time: datetime, exclude_id: int | None = None
    ) -> bool:
        """True when the doctor already has an appointment overlapping the window.

        Two appointments overlap when the second one starts before the first
        one ends. An appointment with no end time runs to the end of the day,
        so it overlaps every window that starts after it.

        This used to be ``q.first()`` on a ``select()``, which is not a method
        SQLAlchemy 2.0 offers on a Select -- every call raised
        ``AttributeError: 'Select' object has no attribute 'first'`` -- and it
        ignored the doctor and the times it was given, so it could not have
        detected a double booking even if it had run.
        """
        from models.appointment import Appointment

        q = select(Appointment.id).filter(
            Appointment.doctor_id == doctor_id,
            Appointment.starts_at < end_time,
            or_(Appointment.ends_at.is_(None), Appointment.ends_at > start_time),
            # A cancelled appointment is not a booking and must not block one.
            or_(
                Appointment.status.is_(None),
                Appointment.status.notin_(('CANCELLED', 'cancelled')),
            ),
        )
        if exclude_id:
            q = q.filter(Appointment.id != exclude_id)
        return db.session.execute(q).first() is not None

    @staticmethod
    def convert_to_visit(appointment, created_by: int | None = None) -> object:
        from models.visit import Visit

        if appointment.status not in (
            AppointmentStatus.CHECKED_IN,
            AppointmentStatus.IN_PROGRESS,
            AppointmentStatus.DONE,
        ):
            raise ValueError('Appointment must be checked-in or in-progress to convert to visit')

        visit = Visit(
            patient_id=appointment.patient_id,
            doctor_id=appointment.doctor_id,
            department_id=appointment.department_id,
            status='registered',
            created_by=created_by,
        )
        db.session.add(visit)
        appointment.status = AppointmentStatus.DONE
        db.session.add(appointment)
        return visit
