"""Waitlist service — shared by the booking and reception blueprints.

Both blueprints used to keep a module-level in-memory list, which lost every
entry on restart and was invisible to the rest of the platform. This service
is the single implementation: entries persist in ``appointment_waitlist`` with
tenant RLS, one active entry per patient per doctor (or unspecified doctor),
and an explicit WAITING -> NOTIFIED -> CONVERTED / CANCELLED lifecycle.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.extensions import db
from app.shared.tenant_filter import TenantIsolationError
from models.appointment import Appointment
from models.appointment_waitlist import (
    WAITLIST_ACTIVE_STATUSES,
    WAITLIST_STATUSES,
    AppointmentWaitlist,
)
from models.department import Department
from models.patient import Patient
from models.user import User

logger = logging.getLogger(__name__)


class WaitlistError(Exception):
    """Raised for client-facing failures; carries the HTTP status to return."""

    def __init__(self, message: str, status: int = 400, **extra: Any):
        super().__init__(message)
        self.message = message
        self.status = status
        self.extra = extra


def get_entry(entry_id: int, tenant_id: int | None) -> AppointmentWaitlist | None:
    """Fetch a waitlist entry scoped to the tenant; None when not found."""
    entry = db.session.get(AppointmentWaitlist, entry_id)
    if entry is None:
        return None
    if tenant_id is not None and getattr(entry, 'tenant_id', None) != tenant_id:
        return None
    return entry


def _validate_reference(model, record_id, tenant_id, label: str):
    record = db.session.get(model, record_id)
    if record is None or (
        tenant_id is not None and getattr(record, 'tenant_id', None) != tenant_id
    ):
        raise WaitlistError(f'{label} not found', 404)
    return record


def add_to_waitlist(
    *,
    patient_id,
    doctor_id=None,
    department_id=None,
    preferred_time=None,
    notes=None,
    tenant_id,
    created_by_id,
) -> dict:
    try:
        patient_id = int(patient_id)
    except (TypeError, ValueError):
        raise WaitlistError('patient_id required') from None
    _validate_reference(Patient, patient_id, tenant_id, 'Patient')
    doctor_id = _optional_int(doctor_id)
    department_id = _optional_int(department_id)
    if doctor_id is not None:
        _validate_reference(User, doctor_id, tenant_id, 'Doctor')
    if department_id is not None:
        _validate_reference(Department, department_id, tenant_id, 'Department')

    # One active entry per patient per doctor (or unspecified doctor) —
    # duplicates would double-book a waitlisted slot.
    dup_q = select(AppointmentWaitlist).where(
        AppointmentWaitlist.patient_id == patient_id,
        AppointmentWaitlist.status.in_(WAITLIST_ACTIVE_STATUSES),
    )
    if doctor_id is None:
        dup_q = dup_q.where(AppointmentWaitlist.doctor_id.is_(None))
    else:
        dup_q = dup_q.where(AppointmentWaitlist.doctor_id == doctor_id)
    existing = db.session.execute(dup_q).scalars().first()
    if existing is not None:
        raise WaitlistError(
            'Patient is already on the waitlist',
            409,
            existing=existing.to_dict(),
        )

    entry = AppointmentWaitlist(
        patient_id=patient_id,
        doctor_id=doctor_id,
        department_id=department_id,
        preferred_time=preferred_time or None,
        status='WAITING',
        notes=notes,
        created_by=created_by_id,
        tenant_id=tenant_id,
    )
    db.session.add(entry)
    try:
        db.session.commit()
    except TenantIsolationError:
        db.session.rollback()
        raise
    except Exception:
        db.session.rollback()
        logger.exception('Error creating waitlist entry')
        raise WaitlistError('Internal server error', 500) from None
    return entry.to_dict()


def list_waitlist(*, tenant_id, status: str | None = None) -> list[dict]:
    q = select(AppointmentWaitlist).order_by(AppointmentWaitlist.created_at.asc())
    if status in WAITLIST_STATUSES:
        q = q.where(AppointmentWaitlist.status == status)
    else:
        q = q.where(AppointmentWaitlist.status.in_(WAITLIST_ACTIVE_STATUSES))
    if tenant_id is not None:
        q = q.where(AppointmentWaitlist.tenant_id == tenant_id)
    items = db.session.execute(q.limit(200)).scalars().all()
    return [item.to_dict() for item in items]


def cancel_waitlist_entry(entry_id: int, tenant_id) -> dict:
    entry = get_entry(entry_id, tenant_id)
    if entry is None:
        raise WaitlistError('Waitlist entry not found', 404)
    if entry.status != 'CANCELLED':
        entry.status = 'CANCELLED'
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            logger.exception('Error cancelling waitlist entry')
            raise WaitlistError('Internal server error', 500) from None
    return entry.to_dict()


def notify_waitlist_entry(entry_id: int, tenant_id, actor_id) -> tuple[dict, bool]:
    """Mark WAITING -> NOTIFIED and queue a real SMS. Returns (entry, sms_queued)."""
    entry = get_entry(entry_id, tenant_id)
    if entry is None:
        raise WaitlistError('Waitlist entry not found', 404)
    if entry.status != 'WAITING':
        raise WaitlistError(
            f'Entry is {entry.status}; only WAITING entries notify', 409
        )
    patient = db.session.get(Patient, entry.patient_id)
    queued = False
    if patient is not None and patient.phone:
        from services.notification_service import NotificationService

        doctor = entry.doctor
        result = NotificationService.add_to_notification_queue(
            user_id=actor_id,
            notification_type='sms',
            recipient=patient.phone,
            subject='توفر موعد',
            content=(
                f'عزيزي {patient.full_name}، تتوفر لديك فرصة حجز موعد'
                f'{" مع الدكتور " + doctor.full_name if doctor else ""}. '
                f'يرجى مراجعة الاستقبال أو الاتصال لحجز الموعد.'
            ),
            variables={'patient_id': patient.id, 'waitlist_id': entry.id},
            priority='high',
            scheduled_at=datetime.now(UTC),
        )
        queued = bool(result and result.get('success'))
    entry.status = 'NOTIFIED'
    entry.notified_at = datetime.now(UTC)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception('Error marking waitlist entry notified')
        raise WaitlistError('Internal server error', 500) from None
    return entry.to_dict(), queued


def convert_waitlist_entry(entry_id: int, tenant_id, starts_at, actor_id) -> tuple[dict, dict]:
    """Convert a waitlisted patient into a SCHEDULED appointment."""
    entry = get_entry(entry_id, tenant_id)
    if entry is None:
        raise WaitlistError('Waitlist entry not found', 404)
    if entry.status in ('CONVERTED', 'CANCELLED'):
        raise WaitlistError(f'Entry already {entry.status}', 409)
    try:
        parsed = datetime.fromisoformat(str(starts_at).replace('Z', '+00:00'))
    except Exception:
        raise WaitlistError('starts_at required (ISO)') from None

    appointment = Appointment(
        tenant_id=tenant_id,
        patient_id=entry.patient_id,
        doctor_id=entry.doctor_id,
        department_id=entry.department_id,
        starts_at=parsed,
        status='SCHEDULED',
        notes=entry.notes,
        created_by=actor_id,
    )
    db.session.add(appointment)
    try:
        db.session.flush()
        entry.status = 'CONVERTED'
        entry.converted_appointment_id = appointment.id
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception('Error converting waitlist entry')
        raise WaitlistError('Internal server error', 500) from None
    return appointment.to_dict(), entry.to_dict()


def _optional_int(value):
    if value in (None, ''):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise WaitlistError('doctor_id/department_id must be integers') from None
