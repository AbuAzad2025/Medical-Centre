"""
Clinical Decision Support (CDS) Alert Routes
"""
from sqlalchemy import select
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from utils.decorators import handle_route_errors, role_required
from models.cds_alert import CDSAlertRule, CDSFiredAlert
from models.patient import Patient
from app.extensions import db

cds_bp = Blueprint('cds', __name__)


@cds_bp.route('/rules')
@login_required
@role_required('admin', 'manager')
@handle_route_errors
def rules():
    items = db.session.execute(select(CDSAlertRule).filter_by(is_active=True).order_by(CDSAlertRule.rule_type)).scalars().all()
    return render_template('cds/rules.html', rules=items)

@cds_bp.route('/alerts')
@login_required
@role_required('doctor', 'nurse', 'admin', 'manager')
@handle_route_errors
def alerts():
    status = request.args.get('status', 'ACTIVE')
    items = db.session.execute(select(CDSFiredAlert).filter_by(is_active=True).order_by(
        CDSFiredAlert.fired_at.desc()
    ).limit(200)).scalars().all()
    return render_template('cds/alerts.html', alerts=items)

@cds_bp.route('/patient/<int:patient_id>/alerts')
@login_required
@role_required('doctor', 'nurse', 'admin')
@handle_route_errors
def patient_alerts(patient_id):
    patient = db.get_or_404(Patient, patient_id)
    alerts = db.session.execute(select(CDSFiredAlert).filter_by(patient_id=patient_id, is_active=True).order_by(
        CDSFiredAlert.fired_at.desc()
    )).scalars().all()
    return render_template('cds/patient_alerts.html', patient=patient, alerts=alerts)
