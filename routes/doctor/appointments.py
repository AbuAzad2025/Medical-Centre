"""appointments routes - extracted from monolithic doctor.py"""

from routes.doctor import doctor_bp

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from utils.decorators import role_required, role_required_json
from models.patient import Patient
from models.visit import Visit
from models.user import User
from models.department import Department
from models.medication import Prescription
from models.lab_request import LabRequest
from models.radiology_request import RadiologyRequest
from models.medical_record import MedicalRecord
from models.appointment import Appointment
from models.follow_up import FollowUpRequest
from models.drug_interaction import DrugInteraction
from models.audit_trail import AuditTrail
from models.system_config import SystemConfig
from app_factory import db
from sqlalchemy import and_, or_, desc, func, case
import logging, json, secrets
from datetime import datetime, date, timedelta, timezone


# =============================================
# APPOINTMENTS ROUTES
# =============================================

@doctor_bp.route('/appointments')
@login_required
@role_required('doctor', 'admin', 'manager')
def appointments():
    """المواعيد — مع إحصائيات وتصفح"""
    try:
        from models.appointment import Appointment
        from sqlalchemy import func
        from app.shared.enums import AppointmentState
        from datetime import date, timedelta

        page = request.args.get('page', 1, type=int)
        per_page = 20
        today = date.today()
        tomorrow = today + timedelta(days=1)

        # Base query
        query = Appointment.query.filter_by(doctor_id=current_user.id).order_by(Appointment.starts_at.desc())
        total = query.count()
        appointments = query.offset((page - 1) * per_page).limit(per_page).all()
        pages = (total + per_page - 1) // per_page if total > 0 else 1

        # Stats
        today_count = Appointment.query.filter(
            Appointment.doctor_id == current_user.id,
            func.date(Appointment.starts_at) == today
        ).count()

        upcoming_count = Appointment.query.filter(
            Appointment.doctor_id == current_user.id,
            func.date(Appointment.starts_at) >= today
        ).count()

        confirmed_count = Appointment.query.filter(
            Appointment.doctor_id == current_user.id,
            Appointment.status == AppointmentState.CONFIRMED
        ).count()

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
    except Exception as e:
        logging.error(f"Error loading appointments: {str(e)}")
        flash('حدث خطأ في تحميل المواعيد', 'error')
        return redirect(url_for('doctor.dashboard'))
