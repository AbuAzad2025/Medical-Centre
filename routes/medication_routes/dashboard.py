"""dashboard routes - extracted from monolithic medication_routes.py"""

from routes.medication_routes import medication_bp

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from utils.decorators import role_required
from models.medication import Medication, Prescription, PharmacySale
from models.patient import Patient
from models.visit import Visit
from models.supply_request import MedicationSupplyRequest, MedicationSupplyRequestItem
from models.drug_interaction import DrugInteraction
from app_factory import db
import logging, json
from datetime import datetime, timezone, timedelta, date
from sqlalchemy import func
from routes.medication_routes.__init__ import (
    get_pharmacy_smart_analytics,
    get_inventory_optimization,
    get_medication_safety_monitoring,
    get_prescription_analytics,
    get_drug_interaction_checker,
    get_pharmacy_workflow_automation,
    get_pharmacy_predictive_insights,
    get_pharmacy_smart_recommendations,
)


# =============================================
# DASHBOARD ROUTES
# =============================================

@medication_bp.route('/')
@login_required
def index():
    return redirect(url_for('medication.dashboard'))

@medication_bp.route('/dashboard')
@login_required
@role_required('doctor', 'nurse', 'pharmacist', 'admin', 'manager')
def dashboard():
    """لوحة تحكم الأدوية"""
    try:
        total_medications = Medication.query.count()
        low_stock_medications = Medication.query.filter(
            Medication.stock_quantity <= Medication.minimum_stock
        ).count()
        today = date.today()
        today_sales = db.session.query(func.coalesce(func.sum(PharmacySale.total_amount), 0)).filter(
            func.date(PharmacySale.created_at) == today
        ).scalar()
        month_sales = db.session.query(func.coalesce(func.sum(PharmacySale.total_amount), 0)).filter(
            func.extract('month', PharmacySale.created_at) == today.month,
            func.extract('year', PharmacySale.created_at) == today.year
        ).scalar()
        expired = Medication.query.filter(
            Medication.expiry_date.isnot(None),
            Medication.expiry_date < today
        ).count()
        today_prescriptions = Prescription.query.filter(
            func.date(Prescription.created_at) == today
        ).count()
        low_stock_list = Medication.query.filter(
            Medication.stock_quantity <= Medication.minimum_stock
        ).limit(10).all()

        pending_prescriptions = Prescription.query.filter(
            Prescription.status == 'active'
        ).order_by(Prescription.created_at.desc()).limit(10).all()

        recent_sales = PharmacySale.query.filter(
            func.date(PharmacySale.created_at) == today
        ).order_by(PharmacySale.created_at.desc()).limit(10).all()

        from app.shared.dashboard_service import render_command_center
        return render_command_center(current_user)
    except Exception as e:
        logging.error(f"Error in medication dashboard: {str(e)}", exc_info=True)
        flash('حدث خطأ في تحميل لوحة التحكم', 'error')
        return redirect(url_for('auth.login'))
