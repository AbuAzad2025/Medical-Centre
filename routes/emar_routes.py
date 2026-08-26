"""
eMAR — Electronic Medication Administration Record Routes
"""

from datetime import date

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from app.shared.enums import eMARAdministrationStatus
from models.emar import eMARAdministration
from models.patient import Patient
from services.nursing_service import NursingService
from utils.decorators import handle_route_errors, role_required

emar_bp = Blueprint('emar', __name__)


@emar_bp.route('/dashboard')
@login_required
@role_required('nurse', 'admin', 'manager')
@handle_route_errors
def dashboard():
    today = date.today()
    administrations = (
        db.session.execute(
            select(eMARAdministration)
            .filter(db.func.date(eMARAdministration.scheduled_time) == today)
            .order_by(eMARAdministration.scheduled_time)
        )
        .scalars()
        .all()
    )
    pending = [a for a in administrations if a.status == eMARAdministrationStatus.SCHEDULED]
    given = [a for a in administrations if a.status == 'GIVEN']
    return render_template(
        'emar/dashboard.html',
        administrations=administrations,
        pending=pending,
        given=given,
        today=today,
    )


@emar_bp.route('/patient/<int:patient_id>')
@login_required
@role_required('nurse', 'doctor', 'admin')
@handle_route_errors
def patient_mar(patient_id):
    patient = db.get_or_404(Patient, patient_id)
    administrations = (
        db.session.execute(
            select(eMARAdministration)
            .filter_by(patient_id=patient_id)
            .order_by(eMARAdministration.scheduled_time.desc())
            .limit(200)
        )
        .scalars()
        .all()
    )
    return render_template(
        'emar/patient_mar.html', patient=patient, administrations=administrations
    )


@emar_bp.route('/administer/<int:admin_id>', methods=['POST'])
@login_required
@role_required('nurse', 'admin')
@handle_route_errors
def administer(admin_id):
    result = NursingService.record_emar_administration(
        admin_id,
        current_user.id,
        status=(request.form.get('status') or 'GIVEN').strip().upper(),
        notes=(request.form.get('notes') or '').strip() or None,
        refusal_reason=(request.form.get('refusal_reason') or '').strip() or None,
        patient_id=request.form.get('patient_id', type=int),
        medication_id=request.form.get('medication_id', type=int),
    )
    if not result.get('success'):
        return jsonify(result), 409
    flash('تم تسجيل إعطاء الدواء بنجاح', 'success')
    return redirect(url_for('emar.dashboard'))
