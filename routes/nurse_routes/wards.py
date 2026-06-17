"""wards routes - extracted from monolithic nurse_routes.py"""

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
# WARDS ROUTES
# =============================================

@nurse_bp.route('/patients')
@login_required
def patients():
    """مرضى التمريض"""
    if current_user.role not in ['nurse', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    return redirect(url_for('nurse.patient_care'))

@nurse_bp.route('/wards')
@login_required
def wards():
    """الأجنحة"""
    if current_user.role not in ['nurse', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('nurse/patient_monitoring.html')
