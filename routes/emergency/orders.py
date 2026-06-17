"""orders routes - extracted from monolithic emergency.py"""

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
# ORDERS ROUTES
# =============================================

@emergency_bp.route('/prescription/<int:emergency_id>', methods=['GET', 'POST'])
@login_required
def prescription(emergency_id):
    """وصفة طبية للطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        emergency = emergency_service.get_case(emergency_id)
        if not emergency:
            flash('حالة الطوارئ غير موجودة', 'error')
            return redirect(url_for('emergency.patient_queue'))
        
        if request.method == 'POST':
            # جمع بيانات الوصفة
            medications = request.form.getlist('medications[]')
            dosages = request.form.getlist('dosages[]')
            frequencies = request.form.getlist('frequencies[]')
            durations = request.form.getlist('durations[]')
            instructions = request.form.getlist('instructions[]')
            
            # إنشاء الوصفة
            prescription_data = []
            for i, medication in enumerate(medications):
                if medication:
                    prescription_data.append({
                        'medication': medication,
                        'dosage': dosages[i] if i < len(dosages) else '',
                        'frequency': frequencies[i] if i < len(frequencies) else '',
                        'duration': durations[i] if i < len(durations) else '',
                        'instructions': instructions[i] if i < len(instructions) else ''
                    })
            
            emergency.prescription = prescription_data
            emergency.prescribed_by = current_user.id
            emergency.prescribed_at = datetime.now(timezone.utc)
            
            db.session.commit()
            flash('تم إنشاء الوصفة بنجاح', 'success')
            return redirect(url_for('emergency.patient_queue'))
        
        return render_template('emergency/prescription.html', emergency=emergency)
    except Exception as e:
        logging.error(f"Error in emergency prescription: {str(e)}")
        flash('حدث خطأ في إنشاء الوصفة', 'error')
        return redirect(url_for('emergency.patient_queue'))

@emergency_bp.route('/lab-request/<int:emergency_id>', methods=['GET', 'POST'])
@login_required
def lab_request(emergency_id):
    """طلب فحوصات للطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        emergency = emergency_service.get_case(emergency_id)
        if not emergency:
            flash('حالة الطوارئ غير موجودة', 'error')
            return redirect(url_for('emergency.patient_queue'))
        
        if request.method == 'POST':
            # جمع بيانات طلب الفحوصات
            tests_requested = request.form.getlist('tests[]')
            urgency = request.form.get('urgency')
            notes = request.form.get('notes')
            
            # إنشاء طلب الفحوصات
            lab_request_data = {
                'tests': tests_requested,
                'urgency': urgency,
                'notes': notes,
                'requested_by': current_user.id,
                'requested_at': datetime.now(timezone.utc)
            }
            
            emergency.lab_request = lab_request_data
            db.session.commit()
            flash('تم إرسال طلب الفحوصات بنجاح', 'success')
            return redirect(url_for('emergency.patient_queue'))
        
        return render_template('emergency/lab_request.html', emergency=emergency)
    except Exception as e:
        logging.error(f"Error in emergency lab request: {str(e)}")
        flash('حدث خطأ في إرسال طلب الفحوصات', 'error')
        return redirect(url_for('emergency.patient_queue'))

@emergency_bp.route('/radiology-request/<int:emergency_id>', methods=['GET', 'POST'])
@login_required
def radiology_request(emergency_id):
    """طلب أشعة للطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        emergency = emergency_service.get_case(emergency_id)
        if not emergency:
            flash('حالة الطوارئ غير موجودة', 'error')
            return redirect(url_for('emergency.patient_queue'))
        
        if request.method == 'POST':
            # جمع بيانات طلب الأشعة
            imaging_type = request.form.get('imaging_type')
            body_part = request.form.get('body_part')
            urgency = request.form.get('urgency')
            clinical_question = request.form.get('clinical_question')
            notes = request.form.get('notes')
            
            # إنشاء طلب الأشعة
            radiology_request_data = {
                'imaging_type': imaging_type,
                'body_part': body_part,
                'urgency': urgency,
                'clinical_question': clinical_question,
                'notes': notes,
                'requested_by': current_user.id,
                'requested_at': datetime.now(timezone.utc)
            }
            
            emergency.radiology_request = radiology_request_data
            db.session.commit()
            flash('تم إرسال طلب الأشعة بنجاح', 'success')
            return redirect(url_for('emergency.patient_queue'))
        
        return render_template('emergency/radiology_request.html', emergency=emergency)
    except Exception as e:
        logging.error(f"Error in emergency radiology request: {str(e)}")
        flash('حدث خطأ في إرسال طلب الأشعة', 'error')
        return redirect(url_for('emergency.patient_queue'))

@emergency_bp.route('/print-prescription/<int:prescription_id>')
@login_required
def print_prescription(prescription_id):
    """طباعة الوصفة الطبية للطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        prescription = db.session.get(Prescription, prescription_id)
        if not prescription:
            flash('الوصفة غير موجودة', 'error')
            return redirect(url_for('emergency.patient_queue'))
        
        return render_template('print/prescription.html',
                             prescription=prescription)
    except Exception as e:
        logging.error(f"Error printing prescription: {str(e)}")
        flash('حدث خطأ في طباعة الوصفة', 'error')
        return redirect(url_for('emergency.patient_queue'))
