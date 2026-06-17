"""dashboard routes - extracted from monolithic medication_routes.py"""

from routes.medication_routes import medication_bp

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from utils.decorators import role_required
from models.medication import Medication, Prescription
from models.patient import Patient
from models.visit import Visit
from models.supply_request import MedicationSupplyRequest, MedicationSupplyRequestItem
from models.drug_interaction import DrugInteraction
from services.core_queries import core_queries
from app_factory import db
import logging, json
from datetime import datetime, timezone, timedelta, date
from sqlalchemy import func


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
        base = core_queries.get_basic_dashboard_stats()
        # إحصائيات الأدوية
        total_medications = Medication.query.count()
        active_medications = Medication.query.filter_by(is_active=True).count()
        low_stock_medications = Medication.query.filter(
            Medication.stock_quantity <= Medication.minimum_stock
        ).count()
        
        # الأدوية منخفضة المخزون
        low_stock = Medication.query.filter(
            Medication.stock_quantity <= Medication.minimum_stock
        ).limit(10).all()
        
        # الأدوية الأكثر استخداماً
        most_used = Medication.query.order_by(
            Medication.stock_quantity.desc()
        ).limit(5).all()

        least_used = Medication.query.order_by(
            Medication.stock_quantity.asc(),
            Medication.trade_name.asc()
        ).limit(5).all()
        
        # الميزات الذكية
        smart_analytics = get_pharmacy_smart_analytics()
        inventory_optimization = get_inventory_optimization()
        safety_monitoring = get_medication_safety_monitoring()
        prescription_analytics = get_prescription_analytics()
        drug_interaction_checker = get_drug_interaction_checker()
        workflow_automation = get_pharmacy_workflow_automation()
        predictive_insights = get_pharmacy_predictive_insights()
        smart_recommendations = get_pharmacy_smart_recommendations()
        
        stats = {
            'total_medications': total_medications,
            'active_medications': active_medications,
            'low_stock_medications': low_stock_medications,
            'low_stock': low_stock,
            'most_used': most_used,
            'least_used': least_used,
            'smart_analytics': smart_analytics,
            'inventory_optimization': inventory_optimization,
            'safety_monitoring': safety_monitoring,
            'prescription_analytics': prescription_analytics,
            'drug_interaction_checker': drug_interaction_checker,
            'workflow_automation': workflow_automation,
            'predictive_insights': predictive_insights,
            'smart_recommendations': smart_recommendations
        }
        
        return render_template('pharmacy/dashboard_new.html', stats=stats)
    except Exception as e:
        logging.error(f"Error in medication dashboard: {str(e)}")
        flash('حدث خطأ في تحميل لوحة التحكم', 'error')
        return redirect(url_for('main.dashboard'))
