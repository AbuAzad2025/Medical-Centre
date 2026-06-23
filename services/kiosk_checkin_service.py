"""Kiosk self check-in — §28.5."""
from __future__ import annotations

from datetime import date, datetime, timezone

from app.shared.enums import AppointmentState


def perform_kiosk_checkin(national_id: str) -> dict:
    """Find patient + today's appointment, create visit, add to queue."""
    from app_factory import db
    from models.appointment import Appointment
    from models.patient import Patient
    from models.visit import Visit
    from routes.reception.queue import add_patient_to_queue_auto

    nid = (national_id or '').strip()
    if len(nid) < 5:
        return {'success': False, 'message': 'أدخل رقم هوية صالحاً'}

    patient = Patient.query.filter_by(national_id=nid).first()
    if not patient:
        return {'success': False, 'message': 'لم يتم العثور على المريض'}

    today = date.today()
    appointment = Appointment.query.filter(
        Appointment.patient_id == patient.id,
        db.func.date(Appointment.starts_at) == today,
        Appointment.status.in_([
            AppointmentState.SCHEDULED,
            AppointmentState.CONFIRMED,
        ]),
    ).order_by(Appointment.starts_at.asc()).first()

    if not appointment:
        return {'success': False, 'message': 'لا يوجد موعد اليوم لهذا المريض'}

    if not appointment.department_id:
        return {'success': False, 'message': 'الموعد بدون قسم — راجع الاستقبال'}

    marker = f'[APPOINTMENT:{appointment.id}]'
    existing = Visit.query.filter(
        Visit.visit_date == today,
        Visit.patient_id == patient.id,
        Visit.notes.ilike(f'%{marker}%'),
    ).first()
    if existing:
        return {
            'success': True,
            'message': 'تم تسجيل الوصول مسبقاً',
            'patient_name': patient.full_name,
            'queue_number': None,
            'visit_id': existing.id,
        }

    visit = Visit(
        patient_id=patient.id,
        department_id=appointment.department_id,
        doctor_id=appointment.doctor_id,
        visit_type='CONSULTATION',
        visit_date=today,
        notes=marker,
        status='OPEN',
        payment_method='CASH',
        payment_status='PENDING',
        is_emergency=False,
        created_by=None,
        currency='ILS',
        created_at=datetime.now(timezone.utc),
    )
    db.session.add(visit)
    db.session.flush()

    if appointment.status == AppointmentState.SCHEDULED:
        appointment.status = AppointmentState.CONFIRMED
    db.session.commit()

    queue_number = None
    q_success, q_msg = add_patient_to_queue_auto(
        visit.id, appointment.department_id, appointment.doctor_id
    )
    if isinstance(q_success, bool) and q_success:
        if 'الرقم' in (q_msg or ''):
            queue_number = (q_msg or '').split('الرقم')[-1].strip()
    elif not isinstance(q_success, bool):
        queue_number = None

    return {
        'success': True,
        'message': q_msg if q_success else 'تم تسجيل الوصول — راجع الاستقبال للطابور',
        'patient_name': patient.full_name,
        'queue_number': queue_number,
        'visit_id': visit.id,
    }
