"""
Telemedicine Routes
"""

import logging
import secrets
from datetime import UTC, datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from models import Patient, TelemedicineAppointment, User
from utils.db_safety import safe_commit, safe_rollback
from utils.decorators import role_required

telemedicine_bp = Blueprint('telemedicine', __name__)


VIEW_ROLES = ('super_admin', 'admin', 'manager', 'reception', 'doctor')


@telemedicine_bp.route('/')
@login_required
def index():
    try:
        status = request.args.get('status', '')
        query = TelemedicineAppointment.query
        if current_user.role == 'doctor':
            query = query.filter_by(doctor_id=current_user.id)
        elif current_user.role not in VIEW_ROLES:
            flash('ليس لديك صلاحية لعرض المواعيد عن بعد', 'error')
            return redirect(url_for('main.dashboard'))
        if status:
            query = query.filter_by(status=status)
        appointments = query.order_by(TelemedicineAppointment.scheduled_start.desc()).all()
        return render_template('telemedicine/index.html', appointments=appointments)
    except Exception as e:
        logging.exception(f'Telemedicine index error: {e!s}')
        flash('حدث خطأ أثناء تحميل المواعيد', 'error')
        return redirect(url_for('main.dashboard'))


@telemedicine_bp.route('/new', methods=['GET', 'POST'])
@login_required
@role_required('doctor', 'reception', 'manager', 'super_admin')
def new_appointment():
    try:
        if request.method == 'POST':
            patient_id = request.form.get('patient_id', type=int)
            doctor_id = request.form.get('doctor_id', type=int)
            scheduled_start = request.form.get('scheduled_start')
            scheduled_end = request.form.get('scheduled_end')
            meeting_provider = request.form.get('meeting_provider', 'jitsi')
            chief_complaint = request.form.get('chief_complaint', '')
            meeting_id = secrets.token_urlsafe(16)
            meeting_url = f'https://meet.jit.si/azad-medical-{meeting_id}'
            tm = TelemedicineAppointment(
                patient_id=patient_id,
                doctor_id=doctor_id,
                scheduled_start=datetime.fromisoformat(scheduled_start)
                if scheduled_start
                else datetime.now(UTC),
                scheduled_end=datetime.fromisoformat(scheduled_end) if scheduled_end else None,
                meeting_provider=meeting_provider,
                meeting_url=meeting_url,
                meeting_id=meeting_id,
                chief_complaint=chief_complaint,
                created_by=current_user.id,
            )
            db.session.add(tm)
            safe_commit(db.session, error_message='database commit failed', reraise=True)
            flash('تم إنشاء الموعد عن بعد بنجاح', 'success')
            return redirect(url_for('telemedicine.index'))
        patients = db.session.execute(select(Patient).limit(100)).scalars().all()
        doctors = db.session.execute(select(User).filter_by(is_active=True)).scalars().all()
        return render_template('telemedicine/new.html', patients=patients, doctors=doctors)
    except Exception as e:
        safe_rollback(db.session, error_message='database rollback')
        logging.exception(f'Telemedicine new appointment error: {e!s}')
        flash('حدث خطأ أثناء إنشاء الموعد', 'error')
        return redirect(url_for('telemedicine.index'))


@telemedicine_bp.route('/<int:tm_id>')
@login_required
def view_appointment(tm_id):
    try:
        tm = db.get_or_404(TelemedicineAppointment, tm_id)
        if current_user.role == 'doctor' and tm.doctor_id != current_user.id:
            flash('ليس لديك صلاحية لعرض هذا الموعد', 'error')
            return redirect(url_for('telemedicine.index'))
        if current_user.role not in VIEW_ROLES:
            flash('ليس لديك صلاحية لعرض الموعد', 'error')
            return redirect(url_for('main.dashboard'))
        return render_template('telemedicine/view.html', tm=tm)
    except Exception as e:
        logging.exception(f'Telemedicine view error: {e!s}')
        flash('حدث خطأ أثناء عرض الموعد', 'error')
        return redirect(url_for('telemedicine.index'))
