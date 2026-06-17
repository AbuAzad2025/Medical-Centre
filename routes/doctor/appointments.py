"""appointments routes - extracted from monolithic doctor.py"""

from routes.doctor import doctor_bp

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from utils.decorators import role_required, role_required_json
from models.patient import Patient
from models.visit import Visit
from models.user import User
from models.department import Department
from models.medication import Prescription
from models.lab_request import LabRequest
from models.radiology_request import RadiologyRequest
from models.medical_record import MedicalRecord
from models.appointment import Appointment
from models.follow_up import FollowUpRequest
from models.drug_interaction import DrugInteraction
from models.audit_trail import AuditTrail
from models.system_config import SystemConfig
from app_factory import db
from sqlalchemy import and_, or_, desc, func, case
import logging, json, secrets
from datetime import datetime, date, timedelta, timezone


# =============================================
# APPOINTMENTS ROUTES
# =============================================

@doctor_bp.route('/appointments')
@login_required
@role_required('doctor', 'admin', 'manager')
def appointments():
    """المواعيد"""
    
    try:
        from models.appointment import Appointment
        
        # جلب مواعيد الطبيب
        appointments = Appointment.query.filter_by(doctor_id=current_user.id).order_by(Appointment.starts_at.desc()).all()
        
        return render_template('doctor/appointments.html', appointments=appointments)
    except Exception as e:
        logging.error(f"Error loading appointments: {str(e)}")
        flash('حدث خطأ في تحميل المواعيد', 'error')
        return redirect(url_for('doctor.dashboard'))
