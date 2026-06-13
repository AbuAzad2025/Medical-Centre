"""
Telemedicine Routes
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from utils.decorators import role_required
from app_factory import db
from models import TelemedicineAppointment, Patient, User
from datetime import datetime, timezone
import secrets

telemedicine_bp = Blueprint('telemedicine', __name__, url_prefix='/telemedicine')


@telemedicine_bp.route('/')
@login_required
def index():
    status = request.args.get('status', '')
    query = TelemedicineAppointment.query
    if status:
        query = query.filter_by(status=status)
    appointments = query.order_by(TelemedicineAppointment.scheduled_start.desc()).all()
    return render_template('telemedicine/index.html', appointments=appointments)


@telemedicine_bp.route('/new', methods=['GET', 'POST'])
@login_required
@role_required('doctor', 'reception', 'manager', 'super_admin')
def new_appointment():
    if request.method == 'POST':
        patient_id = request.form.get('patient_id', type=int)
        doctor_id = request.form.get('doctor_id', type=int)
        scheduled_start = request.form.get('scheduled_start')
        scheduled_end = request.form.get('scheduled_end')
        meeting_provider = request.form.get('meeting_provider', 'jitsi')
        chief_complaint = request.form.get('chief_complaint', '')
        meeting_id = secrets.token_urlsafe(16)
        meeting_url = f"https://meet.jit.si/azad-medical-{meeting_id}"
        tm = TelemedicineAppointment(
            patient_id=patient_id,
            doctor_id=doctor_id,
            scheduled_start=datetime.fromisoformat(scheduled_start) if scheduled_start else datetime.now(timezone.utc),
            scheduled_end=datetime.fromisoformat(scheduled_end) if scheduled_end else None,
            meeting_provider=meeting_provider,
            meeting_url=meeting_url,
            meeting_id=meeting_id,
            chief_complaint=chief_complaint,
            created_by=current_user.id
        )
        db.session.add(tm)
        db.session.commit()
        flash('تم إنشاء الموعد عن بعد بنجاح', 'success')
        return redirect(url_for('telemedicine.index'))
    patients = Patient.query.limit(100).all()
    doctors = User.query.filter_by(is_active=True).all()
    return render_template('telemedicine/new.html', patients=patients, doctors=doctors)


@telemedicine_bp.route('/<int:tm_id>')
@login_required
def view_appointment(tm_id):
    tm = TelemedicineAppointment.query.get_or_404(tm_id)
    return render_template('telemedicine/view.html', tm=tm)
