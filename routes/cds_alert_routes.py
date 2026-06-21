"""
Clinical Decision Support (CDS) Alert Routes
"""
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from utils.decorators import handle_route_errors, role_required
from models.cds_alert import CDSAlertRule, CDSFiredAlert
from models.patient import Patient
from app_factory import db

cds_bp = Blueprint('cds', __name__, guard_module=__name__)

from services.feature_gate_service import guard_module

@cds_bp.before_request
def _guard_doctor_module():
    guard_module('doctor')

@cds_bp.route('/rules')
@login_required
@role_required('admin', 'manager')
@handle_route_errors
def rules():
    items = CDSAlertRule.query.filter_by(is_active=True).order_by(CDSAlertRule.rule_type).all()
    return render_template('cds/rules.html', rules=items)

@cds_bp.route('/alerts')
@login_required
@role_required('doctor', 'nurse', 'admin', 'manager')
@handle_route_errors
def alerts():
    status = request.args.get('status', 'ACTIVE')
    items = CDSFiredAlert.query.filter_by(is_active=True).order_by(
        CDSFiredAlert.fired_at.desc()
    ).limit(200).all()
    return render_template('cds/alerts.html', alerts=items)

@cds_bp.route('/patient/<int:patient_id>/alerts')
@login_required
@role_required('doctor', 'nurse', 'admin')
@handle_route_errors
def patient_alerts(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    alerts = CDSFiredAlert.query.filter_by(patient_id=patient_id, is_active=True).order_by(
        CDSFiredAlert.fired_at.desc()
    ).all()
    return render_template('cds/patient_alerts.html', patient=patient, alerts=alerts)
