"""care routes - extracted from monolithic nurse_routes.py"""

from routes.nurse_routes import nurse_bp

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from utils.decorators import role_required
from models.patient import Patient
from models.visit import Visit
from models.medication import Medication
from services.nursing_service import nursing_service
from app_factory import db
import logging, json
from datetime import datetime, timedelta, timezone, date
from sqlalchemy import func, and_, or_, desc


# =============================================
# CARE ROUTES
# =============================================

@nurse_bp.route('/patient-care')
@login_required
def patient_care():
    """رعاية المرضى"""
    if current_user.role not in ['nurse', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        patients = Patient.query.order_by(desc(Patient.created_at)).limit(20).all()
        
        return render_template('nurse/patient_care.html', patients=patients)
    except Exception as e:
        logging.error(f"Error loading patient care: {str(e)}")
        flash('حدث خطأ في تحميل رعاية المرضى', 'error')
        return redirect(url_for('nurse.dashboard'))

@nurse_bp.route('/patient-monitoring')
@login_required
def patient_monitoring():
    """مراقبة المرضى"""
    if current_user.role not in ['nurse', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        patients = Patient.query.order_by(desc(Patient.created_at)).limit(20).all()
        
        return render_template('nurse/patient_monitoring.html', patients=patients)
    except Exception as e:
        logging.error(f"Error loading patient monitoring: {str(e)}")
        flash('حدث خطأ في تحميل مراقبة المرضى', 'error')
        return redirect(url_for('nurse.dashboard'))
