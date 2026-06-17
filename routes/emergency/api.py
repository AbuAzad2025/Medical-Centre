"""api routes - extracted from monolithic emergency.py"""

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
# API ROUTES
# =============================================

@emergency_bp.route('/api/ems/intake', methods=['POST'])
@login_required
@role_required_json('emergency', 'admin', 'manager')
def api_ems_intake():
    try:
        data = request.get_json() or {}
        name = (data.get('patient_name') or '').strip()
        phone = (data.get('phone') or '').strip()
        complaint = (data.get('chief_complaint') or '').strip() or 'غير محدد'
        severity = (data.get('severity') or 'MODERATE').upper()
        if not name:
            return jsonify({'success': False, 'message': 'اسم المريض مطلوب'}), 400
        parts = [p for p in name.split(' ') if p]
        first_name = parts[0]
        last_name = ' '.join(parts[1:]) if len(parts) > 1 else '-'
        patient = None
        if phone:
            patient = Patient.query.filter_by(phone=phone).first()
        if not patient:
            patient = Patient(first_name=first_name, last_name=last_name, phone=phone or None)
            db.session.add(patient)
            db.session.flush()
        case = EmergencyCase(
            patient_id=patient.id,
            case_number=f"EMS-{int(datetime.now().timestamp())}",
            chief_complaint=complaint,
            severity=severity,
            status='WAITING'
        )
        db.session.add(case)
        db.session.commit()
        return jsonify({'success': True, 'case_id': case.id}), 201
    except Exception as e:
        db.session.rollback()
        logging.error(f"EMS intake error: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر تسجيل الحالة'}), 500
