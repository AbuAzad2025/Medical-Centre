"""
eMAR — Electronic Medication Administration Record Routes
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from utils.decorators import role_required
from models.emar import eMARAdministration, MedicationSchedule
from models.patient import Patient
from models.medication import Prescription, PrescriptionItem
from app_factory import db
from datetime import datetime, date, timezone

emar_bp = Blueprint('emar', __name__)

@emar_bp.route('/dashboard')
@login_required
@role_required('nurse', 'admin', 'manager')
def dashboard():
    today = date.today()
    administrations = eMARAdministration.query.filter(
        db.func.date(eMARAdministration.scheduled_time) == today
    ).order_by(eMARAdministration.scheduled_time).all()
    pending = [a for a in administrations if a.status == 'SCHEDULED']
    given = [a for a in administrations if a.status == 'GIVEN']
    return render_template('emar/dashboard.html',
                           administrations=administrations,
                           pending=pending, given=given, today=today)

@emar_bp.route('/patient/<int:patient_id>')
@login_required
@role_required('nurse', 'doctor', 'admin')
def patient_mar(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    administrations = eMARAdministration.query.filter_by(patient_id=patient_id).order_by(
        eMARAdministration.scheduled_time.desc()
    ).limit(200).all()
    return render_template('emar/patient_mar.html',
                           patient=patient, administrations=administrations)

@emar_bp.route('/administer/<int:admin_id>', methods=['POST'])
@login_required
@role_required('nurse', 'admin')
def administer(admin_id):
    admin = eMARAdministration.query.get_or_404(admin_id)
    admin.status = 'GIVEN'
    admin.administered_time = datetime.now(timezone.utc)
    admin.nurse_id = current_user.id
    db.session.commit()
    flash('تم تسجيل إعطاء الدواء بنجاح', 'success')
    return redirect(url_for('emar.dashboard'))
