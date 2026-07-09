"""reports routes - extracted from monolithic emergency.py"""

from routes.emergency import emergency_bp

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from utils.decorators import role_required, role_required_json
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
from app.shared.print_context import generate_qr_data_uri


# =============================================
# REPORTS ROUTES
# =============================================

@emergency_bp.route('/emergency-report/<int:emergency_id>')
@login_required
@role_required('emergency', 'manager')
def emergency_report(emergency_id):
    """تقرير الطوارئ"""
    
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
@role_required('emergency', 'manager')
def print_emergency_report(emergency_id):
    """طباعة تقرير الطوارئ"""
    
    try:
        emergency = emergency_service.get_case(emergency_id)
        if not emergency:
            flash('حالة الطوارئ غير موجودة', 'error')
            return redirect(url_for('emergency.patient_queue'))
        
        qr_data_uri = generate_qr_data_uri(
            f"ER|{emergency.id}|{emergency.patient_id}|{emergency.created_at.isoformat() if emergency.created_at else ''}"
        )
        return render_template('print/emergency_report.html',
                             emergency=emergency,
                             qr_data_uri=qr_data_uri)
    except Exception as e:
        logging.error(f"Error printing emergency report: {str(e)}")
        flash('حدث خطأ في طباعة تقرير الطوارئ', 'error')
        return redirect(url_for('emergency.patient_queue'))

# ==================== الميزات الذكية للطوارئ ====================
