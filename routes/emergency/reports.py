"""reports routes - extracted from monolithic emergency.py"""

from routes.emergency import emergency_bp

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from utils.decorators import role_required_json
from models.patient import Patient
from models.visit import Visit
from models.user import User
from models.department import Department
from models.emergency import EmergencyCase
from models.medication import Prescription
from models.lab_request import LabRequest
from models.radiology_request import RadiologyRequest
from models.medical_record import MedicalRecord
from services.emergency_service import emergency_service
from app_factory import db
from sqlalchemy import and_, or_, desc, case
import logging, json
from datetime import datetime, date, timedelta, timezone


# =============================================
# REPORTS ROUTES
# =============================================

@emergency_bp.route('/emergency-report/<int:emergency_id>')
@login_required
def emergency_report(emergency_id):
    """تقرير الطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        emergency = emergency_service.get_case(emergency_id)
        if not emergency:
            flash('حالة الطوارئ غير موجودة', 'error')
            return redirect(url_for('emergency.patient_queue'))
        return render_template('emergency/emergency_report.html', emergency=emergency)
    except Exception as e:
        logging.error(f"Error generating emergency report: {str(e)}")
        flash('حدث خطأ في إنشاء تقرير الطوارئ', 'error')
        return redirect(url_for('emergency.patient_queue'))

@emergency_bp.route('/print-emergency-report/<int:emergency_id>')
@login_required
def print_emergency_report(emergency_id):
    """طباعة تقرير الطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        emergency = emergency_service.get_case(emergency_id)
        if not emergency:
            flash('حالة الطوارئ غير موجودة', 'error')
            return redirect(url_for('emergency.patient_queue'))
        
        return render_template('print/emergency_report.html',
                             emergency=emergency)
    except Exception as e:
        logging.error(f"Error printing emergency report: {str(e)}")
        flash('حدث خطأ في طباعة تقرير الطوارئ', 'error')
        return redirect(url_for('emergency.patient_queue'))

# ==================== الميزات الذكية للطوارئ ====================
