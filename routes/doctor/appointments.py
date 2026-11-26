"""appointments routes - extracted from monolithic doctor.py"""

import logging

# Imports
from flask import flash, g, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from routes.doctor import doctor_bp
from utils.decorators import role_required

# APPOINTMENTS ROUTES


@doctor_bp.route('/appointments')
@login_required
@role_required('doctor', 'admin', 'manager')
def appointments():
    """المواعيد — مع إحصائيات وتصفح"""
    try:
        from datetime import date

        from sqlalchemy import func

        from app.shared.enums import AppointmentState
        from models.appointment import Appointment

        page = request.args.get('page', 1, type=int)
        per_page = 20
        today = date.today()

        # Base query
        query = select(Appointment).filter(
            Appointment.doctor_id == current_user.id,
            Appointment.tenant_id == g.tenant_id
            if hasattr(Appointment, 'tenant_id') and g.tenant_id
            else True,
        )
        total = db.session.execute(select(func.count()).select_from(query.subquery())).scalar()
        appointments = (
            db.session.execute(query.offset((page - 1) * per_page).limit(per_page)).scalars().all()
        )
        pages = (total + per_page - 1) // per_page if total > 0 else 1

        # Stats
        today_count = db.session.execute(
            select(func.count())
            .select_from(Appointment)
            .filter(
                Appointment.doctor_id == current_user.id, func.date(Appointment.starts_at) == today
            )
        ).scalar()

        upcoming_count = db.session.execute(
            select(func.count())
            .select_from(Appointment)
            .filter(
                Appointment.doctor_id == current_user.id, func.date(Appointment.starts_at) >= today
            )
        ).scalar()

        confirmed_count = db.session.execute(
            select(func.count())
            .select_from(Appointment)
            .filter(
                Appointment.doctor_id == current_user.id,
                Appointment.status == AppointmentState.CONFIRMED,
            )
        ).scalar()

        # A solo clinic has no reception to convert public bookings into
        # Appointment rows, so show the tenant's online bookings here instead.
        if not appointments and 'reception' not in getattr(g, 'enabled_modules', set()):
            from datetime import datetime
            from types import SimpleNamespace

            from models.online_booking import OnlineBooking

            bookings = (
                db.session.execute(
                    select(OnlineBooking)
                    .filter_by(tenant_id=g.tenant_id)
                    .order_by(OnlineBooking.appointment_date.desc())
                    .limit(per_page)
                )
                .scalars()
                .all()
            )
            appointments = [
                SimpleNamespace(
                    id=b.id,
                    patient=SimpleNamespace(
                        full_name=f'{b.first_name or ""} {b.last_name or ""}'.strip() or '—',
                        phone=b.phone,
                    ),
                    starts_at=datetime.combine(b.appointment_date, b.appointment_time)
                    if b.appointment_date and b.appointment_time
                    else None,
                    status={
                        'pending': 'SCHEDULED',
                        'cancelled': 'CANCELLED',
                        'confirmed': 'CONFIRMED',
                    }.get((b.status or '').lower(), 'SCHEDULED'),
                    visit_id=None,
                )
                for b in bookings
            ]
            total = len(appointments)
            pages = 1
            today_count = len([b for b in bookings if b.appointment_date == today])
            upcoming_count = len([b for b in bookings if b.appointment_date >= today])
            confirmed_count = len([b for b in bookings if (b.status or '').lower() == 'confirmed'])

        return render_template(
            'doctor/appointments.html',
            appointments=appointments,
            total=total,
            today_count=today_count,
            upcoming_count=upcoming_count,
            confirmed_count=confirmed_count,
            page=page,
            pages=pages,
        )
    except Exception:
        logging.exception('Error loading appointments')
        flash('حدث خطأ في تحميل المواعيد', 'error')
        return redirect(url_for('doctor.dashboard'))
