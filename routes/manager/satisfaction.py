"""satisfaction routes - extracted from monolithic manager.py"""

from routes.manager import manager_bp

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from utils.decorators import manager_or_admin_only, can_approve_force_payment, prevent_self_approval, role_required, role_required_json
from models.patient import Patient
from models.visit import Visit
from models.user import User, StaffWorkSchedule, StaffAbsence
from models.department import Department
from models.payment import Payment
from models.invoice import Invoice
from models.appointment import Appointment
from models.lab_request import LabRequest
from models.radiology_request import RadiologyRequest
from services.gatekeeper_service import GatekeeperService
from services.manager_service import manager_service
from app_factory import db
from sqlalchemy import func
from decimal import Decimal, ROUND_HALF_UP
import logging
from datetime import datetime, date, timedelta, timezone


# =============================================
# SATISFACTION ROUTES
# =============================================

@manager_bp.route('/patient-satisfaction')
@login_required
@role_required('manager', 'admin', 'super_admin')
def patient_satisfaction_dashboard():
    """لوحة رضا المرضى"""
    try:
        from models.patient_satisfaction import PatientSatisfactionSurvey
        surveys = PatientSatisfactionSurvey.query.order_by(PatientSatisfactionSurvey.created_at.desc()).limit(100).all()
        total = len(surveys) if surveys else 0
        if total > 0:
            avg_score = sum(float(s.overall_satisfaction or 0) for s in surveys) / total
            avg_recommend = sum(float(s.recommend_likelihood or 0) for s in surveys) / total
            promoters = sum(1 for s in surveys if float(s.recommend_likelihood or 0) >= 9)
            detractors = sum(1 for s in surveys if float(s.recommend_likelihood or 0) <= 6)
            nps = round(((promoters - detractors) / total) * 100, 1)
        else:
            avg_score = avg_recommend = nps = 0
        return render_template('manager/patient_satisfaction.html', surveys=surveys, total=total,
                               avg_score=round(avg_score, 1), avg_recommend=round(avg_recommend, 1), nps=nps)
    except Exception:
        return render_template('manager/patient_satisfaction.html', surveys=[], total=0,
                               avg_score=0, avg_recommend=0, nps=0)
