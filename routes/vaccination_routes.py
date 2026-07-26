"""
Vaccination / Immunization Registry Routes
"""
from sqlalchemy import select
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from utils.decorators import handle_route_errors, role_required
from models.vaccination import Vaccine, Immunization, VaccinationSchedule
from models.patient import Patient
from app.extensions import db
from datetime import date

vaccination_bp = Blueprint('vaccination', __name__)


@vaccination_bp.route('/vaccines')
@login_required
@role_required('nurse', 'doctor', 'admin', 'manager')
@handle_route_errors
def vaccines():
    items = db.session.execute(select(Vaccine).filter_by(is_active=True).order_by(Vaccine.name)).scalars().all()
    return render_template('vaccination/vaccines.html', vaccines=items)

@vaccination_bp.route('/patient/<int:patient_id>')
@login_required
@role_required('nurse', 'doctor', 'admin', 'receptionist')
@handle_route_errors
def patient_immunizations(patient_id):
    patient = db.get_or_404(Patient, patient_id)
    immunizations = db.session.execute(select(Immunization).filter_by(patient_id=patient_id).order_by(
        Immunization.administration_date.desc()
    )).scalars().all()
    # Calculate upcoming vaccinations
    upcoming = []
    for imm in immunizations:
        if imm.next_due_date and imm.next_due_date >= date.today():
            upcoming.append(imm)
    return render_template('vaccination/patient_immunizations.html',
                           patient=patient, immunizations=immunizations, upcoming=upcoming)
