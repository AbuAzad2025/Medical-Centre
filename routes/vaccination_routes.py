"""
Vaccination / Immunization Registry Routes
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from utils.decorators import handle_route_errors, role_required
from models.vaccination import Vaccine, Immunization, VaccinationSchedule
from models.patient import Patient
from app_factory import db
from datetime import date

vaccination_bp = Blueprint('vaccination', __name__, guard_module=__name__)

from services.feature_gate_service import guard_module

@vaccination_bp.before_request
def _guard_doctor_module():
    guard_module('doctor')

@vaccination_bp.route('/vaccines')
@login_required
@role_required('nurse', 'doctor', 'admin', 'manager')
@handle_route_errors
def vaccines():
    items = Vaccine.query.filter_by(is_active=True).order_by(Vaccine.name).all()
    return render_template('vaccination/vaccines.html', vaccines=items)

@vaccination_bp.route('/patient/<int:patient_id>')
@login_required
@role_required('nurse', 'doctor', 'admin', 'receptionist')
@handle_route_errors
def patient_immunizations(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    immunizations = Immunization.query.filter_by(patient_id=patient_id).order_by(
        Immunization.administration_date.desc()
    ).all()
    # Calculate upcoming vaccinations
    upcoming = []
    for imm in immunizations:
        if imm.next_due_date and imm.next_due_date >= date.today():
            upcoming.append(imm)
    return render_template('vaccination/patient_immunizations.html',
                           patient=patient, immunizations=immunizations, upcoming=upcoming)
