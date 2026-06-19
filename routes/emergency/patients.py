"""patients routes - extracted from monolithic emergency.py"""

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
# PATIENTS ROUTES
# =============================================

@emergency_bp.route('/patient-details/<int:emergency_id>')
@login_required
def patient_details(emergency_id):
    """تفاصيل حالة الطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        emergency = emergency_service.get_case(emergency_id)
        if not emergency:
            flash('حالة الطوارئ غير موجودة', 'error')
            return redirect(url_for('emergency.patient_queue'))
        
        # جلب السجل الطبي للمريض
        medical_records = MedicalRecord.query.filter(
            MedicalRecord.patient_id == emergency.patient_id
        ).order_by(desc(MedicalRecord.created_at)).limit(10).all()
        
        # جلب الوصفات السابقة
        previous_prescriptions = Prescription.query.filter(
            Prescription.patient_id == emergency.patient_id
        ).order_by(desc(Prescription.created_at)).limit(5).all()
        
        # جلب طلبات المختبر والأشعة
        lab_requests = LabRequest.query.filter(
            LabRequest.visit_id == emergency.visit_id
        ).all()
        
        radiology_requests = RadiologyRequest.query.filter(
            RadiologyRequest.visit_id == emergency.visit_id
        ).all()
        
        return render_template('emergency/patient_details.html',
                             emergency=emergency,
                             medical_records=medical_records,
                             previous_prescriptions=previous_prescriptions,
                             lab_requests=lab_requests,
                             radiology_requests=radiology_requests)
    except Exception as e:
        logging.error(f"Error loading patient details: {str(e)}")
        flash('حدث خطأ في تحميل تفاصيل المريض', 'error')
        return redirect(url_for('emergency.patient_queue'))

# مسارات إضافية للطوارئ الاحترافية

@emergency_bp.route('/medical-history/<int:patient_id>')
@login_required
def medical_history(patient_id):
    """السجل الطبي للمريض في الطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        patient = db.session.get(Patient, patient_id)
        if not patient:
            flash('المريض غير موجود', 'error')
            return redirect(url_for('emergency.patient_queue'))
        
        # جلب السجل الطبي الكامل
        medical_records = MedicalRecord.query.filter(
            MedicalRecord.patient_id == patient_id
        ).order_by(desc(MedicalRecord.created_at)).all()
        
        # جلب حالات الطوارئ السابقة
        previous_emergencies = EmergencyCase.query.filter(
            EmergencyCase.patient_id == patient_id,
            EmergencyCase.status == 'COMPLETED'
        ).order_by(desc(EmergencyCase.created_at)).limit(10).all()
        
        return render_template('emergency/medical_history.html',
                             patient=patient,
                             medical_records=medical_records,
                             previous_emergencies=previous_emergencies)
    except Exception as e:
        logging.error(f"Error loading medical history: {str(e)}")
        flash('حدث خطأ في تحميل السجل الطبي', 'error')
        return redirect(url_for('emergency.patient_queue'))

@emergency_bp.route('/prescriptions-history/<int:patient_id>')
@login_required
def prescriptions_history(patient_id):
    """تاريخ الوصفات الطبية للمريض في الطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        patient = db.session.get(Patient, patient_id)
        if not patient:
            flash('المريض غير موجود', 'error')
            return redirect(url_for('emergency.patient_queue'))
        
        # جلب الوصفات السابقة
        prescriptions = Prescription.query.filter(
            Prescription.patient_id == patient_id
        ).order_by(desc(Prescription.created_at)).all()
        
        return render_template('emergency/prescriptions_history.html',
                             patient=patient,
                             prescriptions=prescriptions)
    except Exception as e:
        logging.error(f"Error loading prescriptions history: {str(e)}")
        flash('حدث خطأ في تحميل تاريخ الوصفات', 'error')
        return redirect(url_for('emergency.patient_queue'))

@emergency_bp.route('/lab-results/<int:patient_id>')
@login_required
def lab_results(patient_id):
    """نتائج المختبر للمريض في الطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        patient = db.session.get(Patient, patient_id)
        if not patient:
            flash('المريض غير موجود', 'error')
            return redirect(url_for('emergency.patient_queue'))
        
        # جلب نتائج المختبر
        lab_requests = LabRequest.query.filter(
            LabRequest.patient_id == patient_id
        ).order_by(desc(LabRequest.created_at)).all()
        
        return render_template('emergency/lab_results.html',
                             patient=patient,
                             lab_requests=lab_requests)
    except Exception as e:
        logging.error(f"Error loading lab results: {str(e)}")
        flash('حدث خطأ في تحميل نتائج المختبر', 'error')
        return redirect(url_for('emergency.patient_queue'))

@emergency_bp.route('/radiology-results/<int:patient_id>')
@login_required
def radiology_results(patient_id):
    """نتائج الأشعة للمريض في الطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        patient = db.session.get(Patient, patient_id)
        if not patient:
            flash('المريض غير موجود', 'error')
            return redirect(url_for('emergency.patient_queue'))
        
        # جلب نتائج الأشعة
        radiology_requests = RadiologyRequest.query.filter(
            RadiologyRequest.patient_id == patient_id
        ).order_by(desc(RadiologyRequest.created_at)).all()
        
        return render_template('emergency/radiology_results.html',
                             patient=patient,
                             radiology_requests=radiology_requests)
    except Exception as e:
        logging.error(f"Error loading radiology results: {str(e)}")
        flash('حدث خطأ في تحميل نتائج الأشعة', 'error')
        return redirect(url_for('emergency.patient_queue'))
