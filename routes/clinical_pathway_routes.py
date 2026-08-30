"""
Clinical Pathways / Care Plans Routes
"""

from flask import Blueprint, abort, render_template
from flask_login import login_required
from sqlalchemy import select

from app.extensions import db
from models.clinical_pathway import (
    ClinicalPathway,
    ClinicalPathwayStep,
    PatientCarePlan,
)
from models.patient import Patient
from utils.decorators import handle_route_errors, role_required
from utils.tenant_query import TenantContextError, get_tenant_record

pathway_bp = Blueprint('pathway', __name__)


@pathway_bp.route('/pathways')
@login_required
@role_required('doctor', 'admin', 'manager')
@handle_route_errors
def pathways():
    items = (
        db.session.execute(
            select(ClinicalPathway).filter_by(is_active=True).order_by(ClinicalPathway.name)
        )
        .scalars()
        .all()
    )
    return render_template('pathway/pathways.html', pathways=items)


@pathway_bp.route('/pathway/<int:pathway_id>')
@login_required
@role_required('doctor', 'admin', 'manager')
@handle_route_errors
def pathway_detail(pathway_id):
    pathway = db.get_or_404(ClinicalPathway, pathway_id)
    steps = (
        db.session.execute(
            select(ClinicalPathwayStep)
            .filter_by(pathway_id=pathway_id, is_active=True)
            .order_by(ClinicalPathwayStep.step_number)
        )
        .scalars()
        .all()
    )
    return render_template('pathway/pathway_detail.html', pathway=pathway, steps=steps)


@pathway_bp.route('/patient/<int:patient_id>/care-plans')
@login_required
@role_required('doctor', 'nurse', 'admin', 'manager')
@handle_route_errors
def patient_care_plans(patient_id):
    try:
        patient = get_tenant_record(Patient, patient_id)
    except TenantContextError:
        abort(404)
    plans = (
        db.session.execute(
            select(PatientCarePlan)
            .filter_by(patient_id=patient_id, is_active=True)
            .order_by(PatientCarePlan.start_date.desc())
        )
        .scalars()
        .all()
    )
    return render_template('pathway/patient_care_plans.html', patient=patient, plans=plans)
