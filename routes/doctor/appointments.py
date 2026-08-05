"""appointments routes - extracted from monolithic doctor.py"""

import logging

# Imports
from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from routes.doctor import doctor_bp
from utils.decorators import role_required

# =============================================
# APPOINTMENTS ROUTES
# =============================================


@doctor_bp.route('/appointments')
@login_required
@role_required('doctor', 'admin', 'manager')
def appointments():
    """المواعيد — مع إحصائيات وتصفح"""
    try:
        from datetime import date, timedelta

        from sqlalchemy import func

        from app.shared.enums import AppointmentState
        from models.appointment import Appointment

        page = request.args.get('page', 1, type=int)
        per_page = 20
        today = date.today()
        today + timedelta(days=1)

        # Base query
        query = select(Appointment).filter_by(doctor_id=current_user.id)
        total = query.count()
        appointments = query.offset((page - 1) * per_page).limit(per_page).all()
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
        logging.exception('Error loading appointments: %s')
        flash('حدث خطأ في تحميل المواعيد', 'error')
        return redirect(url_for('doctor.dashboard'))
