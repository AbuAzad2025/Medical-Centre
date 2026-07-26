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
from app.extensions import db
import logging, json
from datetime import datetime, timezone, timedelta, date
from sqlalchemy import func, select
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
        tid = current_user.tenant_id
        total_medications = db.session.execute(select(func.count()).select_from(Medication).filter(Medication.tenant_id == tid)).scalar()
        low_stock_medications = db.session.execute(select(func.count()).select_from(Medication).filter(
            Medication.stock_quantity <= Medication.minimum_stock,
            Medication.tenant_id == tid
        )).scalar()
        today = date.today()
        today_sales = db.session.execute(select(func.coalesce(func.sum(PharmacySale.total_amount), 0)).filter(
            func.date(PharmacySale.created_at) == today,
            PharmacySale.tenant_id == tid
        )).scalar()
        month_sales = db.session.execute(select(func.coalesce(func.sum(PharmacySale.total_amount), 0)).filter(
            func.extract('month', PharmacySale.created_at) == today.month,
            func.extract('year', PharmacySale.created_at) == today.year,
            PharmacySale.tenant_id == tid
        )).scalar()
        expired = db.session.execute(select(func.count()).select_from(Medication).filter(
            Medication.expiry_date.isnot(None),
            Medication.expiry_date < today,
            Medication.tenant_id == tid
        )).scalar()
        today_prescriptions = db.session.execute(select(func.count()).select_from(Prescription).filter(
            func.date(Prescription.created_at) == today,
            Prescription.tenant_id == tid
        )).scalar()
        low_stock_list = db.session.execute(select(Medication).filter(
            Medication.stock_quantity <= Medication.minimum_stock,
            Medication.tenant_id == tid
        ).limit(10)).scalars().all()

        pending_prescriptions = db.session.execute(select(Prescription).filter(
            Prescription.status == 'active',
            Prescription.tenant_id == tid
        ).order_by(Prescription.created_at.desc()).limit(10)).scalars().all()

        recent_sales = db.session.execute(select(PharmacySale).filter(
            func.date(PharmacySale.created_at) == today,
            PharmacySale.tenant_id == tid
        ).order_by(PharmacySale.created_at.desc()).limit(10)).scalars().all()

        from app.shared.dashboard_service import render_command_center
        return render_command_center(current_user)
    except Exception as e:
        logging.error(f"Error in medication dashboard: {str(e)}", exc_info=True)
        flash('حدث خطأ في تحميل لوحة التحكم', 'error')
        return redirect(url_for('auth.login'))
