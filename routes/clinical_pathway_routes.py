"""
Clinical Pathways / Care Plans Routes
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from utils.decorators import handle_route_errors, role_required
from models.clinical_pathway import ClinicalPathway, ClinicalPathwayStep, PatientCarePlan, CarePlanTask
from models.patient import Patient
from app_factory import db

pathway_bp = Blueprint('pathway', __name__)


@pathway_bp.route('/pathways')
@login_required
@role_required('doctor', 'admin', 'manager')
@handle_route_errors
def pathways():
    items = ClinicalPathway.query.filter_by(is_active=True).order_by(ClinicalPathway.name).all()
    return render_template('pathway/pathways.html', pathways=items)

@pathway_bp.route('/pathway/<int:pathway_id>')
@login_required
@role_required('doctor', 'admin', 'manager')
@handle_route_errors
def pathway_detail(pathway_id):
    pathway = ClinicalPathway.query.get_or_404(pathway_id)
    steps = ClinicalPathwayStep.query.filter_by(pathway_id=pathway_id, is_active=True).order_by(
        ClinicalPathwayStep.step_number
    ).all()
    return render_template('pathway/pathway_detail.html', pathway=pathway, steps=steps)

@pathway_bp.route('/patient/<int:patient_id>/care-plans')
@login_required
@role_required('doctor', 'nurse', 'admin')
@handle_route_errors
def patient_care_plans(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    plans = PatientCarePlan.query.filter_by(patient_id=patient_id, is_active=True).order_by(
        PatientCarePlan.start_date.desc()
    ).all()
    return render_template('pathway/patient_care_plans.html', patient=patient, plans=plans)
