"""
Vaccination / Immunization Registry Routes
"""

from datetime import date

from flask import Blueprint, render_template
from flask_login import login_required
from sqlalchemy import select

from app.extensions import db
from models.patient import Patient
from models.vaccination import Immunization, Vaccine
from utils.decorators import handle_route_errors, role_required

vaccination_bp = Blueprint('vaccination', __name__)


@vaccination_bp.route('/vaccines')
@login_required
@role_required('nurse', 'doctor', 'admin', 'manager')
@handle_route_errors
def vaccines():
    items = (
        db.session.execute(select(Vaccine).filter_by(is_active=True).order_by(Vaccine.name))
        .scalars()
        .all()
    )
    return render_template('vaccination/vaccines.html', vaccines=items)


@vaccination_bp.route('/patient/<int:patient_id>')
@login_required
@role_required('nurse', 'doctor', 'admin', 'receptionist')
@handle_route_errors
def patient_immunizations(patient_id):
    patient = db.get_or_404(Patient, patient_id)
    immunizations = (
        db.session.execute(
            select(Immunization)
            .filter_by(patient_id=patient_id)
            .order_by(Immunization.administration_date.desc())
        )
        .scalars()
        .all()
    )
    # Calculate upcoming vaccinations
    upcoming = []
    for imm in immunizations:
        if imm.next_due_date and imm.next_due_date >= date.today():
            upcoming.append(imm)
    return render_template(
        'vaccination/patient_immunizations.html',
        patient=patient,
        immunizations=immunizations,
        upcoming=upcoming,
    )
