"""treatment routes - extracted from monolithic emergency.py"""

from routes.emergency import emergency_bp, _set_emergency_status

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
from app.shared.enums import EmergencyStatus
from services.emergency_service import emergency_service
from app_factory import db
from sqlalchemy import and_, or_, desc, case
import logging, json
from datetime import datetime, date, timedelta, timezone


# =============================================
# TREATMENT ROUTES
# =============================================

@emergency_bp.route('/treatment/<int:emergency_id>', methods=['GET', 'POST'])
@login_required
def treatment(emergency_id):
    """علاج الطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        emergency = emergency_service.get_case(emergency_id)
        if not emergency:
            flash('حالة الطوارئ غير موجودة', 'error')
            return redirect(url_for('emergency.patient_queue'))
        
        if request.method == 'POST':
            # جمع بيانات العلاج
            chief_complaint = request.form.get('chief_complaint')
            diagnosis = request.form.get('diagnosis')
            treatment_given = request.form.get('treatment_given')
            medications = request.form.get('medications')
            procedures = request.form.get('procedures')
            treatment_notes = request.form.get('treatment_notes')
            
            # تحديث حالة الطوارئ
            emergency.chief_complaint = chief_complaint
            emergency.diagnosis = diagnosis
            emergency.treatment_given = treatment_given
            emergency.medications = medications
            emergency.procedures = procedures
            emergency.treatment_notes = treatment_notes
            _set_emergency_status(emergency, 'OBSERVATION')
            emergency.treated_by = current_user.id
            emergency.treated_at = datetime.now(timezone.utc)
            
            db.session.commit()
            flash('تم تسجيل العلاج بنجاح', 'success')
            return redirect(url_for('emergency.patient_queue'))
        
        return render_template('emergency/emergency_treatment.html', emergency=emergency)
    except Exception as e:
        logging.error(f"Error in emergency treatment: {str(e)}")
        flash('حدث خطأ في تسجيل العلاج', 'error')
        return redirect(url_for('emergency.patient_queue'))

@emergency_bp.route('/end-treatment/<int:emergency_id>', methods=['POST'])
@login_required
def end_treatment(emergency_id):
    """إنهاء العلاج في الطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        emergency = emergency_service.get_case(emergency_id)
        if not emergency:
            flash('حالة الطوارئ غير موجودة', 'error')
            return redirect(url_for('emergency.patient_queue'))
        
        # إنهاء العلاج
        _set_emergency_status(emergency, 'COMPLETED')
        emergency.completed_at = datetime.now(timezone.utc)
        emergency.completed_by = current_user.id
        
        # إخطار الاستقبال لإتمام إجراءات الزيارة المرتبطة دون تعديل الحالة مباشرة
        try:
            if emergency.visit:
                from services.notification_service import NotificationService
                NotificationService.send_notification(
                    recipient_role='reception',
                    recipient_department_id=emergency.visit.department_id,
                    title='إنهاء علاج حالة طوارئ',
                    message=f"زيارة رقم {emergency.visit.id} المرتبطة بحالة الطوارئ {emergency_id} تم إنهاء علاجها - يرجى إتمام الإجراءات",
                    notification_type='warning',
                    sender_id=current_user.id
                )
        except Exception as e:

            logging.warning(f"Error in {__name__}: {e}")
        db.session.commit()
        flash('تم إنهاء العلاج بنجاح وإخطار الاستقبال', 'success')
        return redirect(url_for('emergency.patient_queue'))
    except Exception as e:
        logging.error(f"Error ending emergency treatment: {str(e)}")
        flash('حدث خطأ في إنهاء العلاج', 'error')
        return redirect(url_for('emergency.patient_queue'))

@emergency_bp.route('/start-treatment/<int:emergency_id>', methods=['POST'])
@login_required
def start_treatment(emergency_id):
    """بدء علاج حالة الطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        emergency = emergency_service.get_case(emergency_id)
        if not emergency:
            flash('حالة الطوارئ غير موجودة', 'error')
            return redirect(url_for('emergency.patient_queue'))
        
        # تحديث حالة الطوارئ
        _set_emergency_status(emergency, 'TREATMENT')
        emergency.treatment_started_at = datetime.now(timezone.utc)
        emergency.treated_by = current_user.id
        
        db.session.commit()
        
        flash('تم بدء العلاج بنجاح', 'success')
        return redirect(url_for('emergency.patient_details', emergency_id=emergency_id))
    except Exception as e:
        logging.error(f"Error starting treatment: {str(e)}")
        flash('حدث خطأ في بدء العلاج', 'error')
        return redirect(url_for('emergency.patient_queue'))

@emergency_bp.route('/emergency-visits')
@login_required
def emergency_visits():
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    try:
        visits = Visit.query.filter(Visit.visit_type == 'EMERGENCY').order_by(desc(Visit.created_at)).all()
        return render_template('emergency/emergency_visits.html', visits=visits)
    except Exception as e:
        logging.error(f"Error loading emergency visits: {str(e)}")
        flash('حدث خطأ في تحميل زيارات الطوارئ', 'error')
        return redirect(url_for('emergency.dashboard'))

@emergency_bp.route('/emergency-treatment/<int:visit_id>', methods=['GET', 'POST'])
@login_required
def emergency_treatment(visit_id):
    if current_user.role not in ['emergency', 'doctor', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    try:
        visit = db.session.get(Visit, visit_id)
        if not visit:
            if request.method == 'POST':
                return jsonify({'success': False, 'error': 'الزيارة غير موجودة'}), 404
            flash('الزيارة غير موجودة', 'error')
            return redirect(url_for('emergency.emergency_visits'))
        if request.method == 'POST':
            diagnosis = request.form.get('emergency_diagnosis')
            procedures = request.form.get('emergency_procedures')
            notes = request.form.get('notes')
            if diagnosis:
                visit.diagnosis = diagnosis
            if procedures:
                visit.treatment_plan = procedures
            if notes:
                visit.notes = notes
            # إشعار الاستقبال ببدء علاج الطوارئ دون تعديل حالة الزيارة مباشرة
            try:
                from services.notification_service import NotificationService
                NotificationService.send_notification(
                    recipient_role='reception',
                    recipient_department_id=visit.department_id,
                    title='بدء علاج زيارة طوارئ',
                    message=f"تم تسجيل علاج إسعافي للزيارة رقم {visit.id}",
                    notification_type='info',
                    sender_id=current_user.id
                )
            except Exception as e:

                logging.warning(f"Error in {__name__}: {e}")
            db.session.commit()
            return jsonify({'success': True})
        return render_template('emergency/emergency_treatment.html', visit=visit)
    except Exception as e:
        logging.error(f"Error in emergency treatment: {str(e)}")
        if request.method == 'POST':
            return jsonify({'success': False, 'error': 'حدث خطأ أثناء حفظ العلاج الإسعافي'}), 500
        flash('حدث خطأ في تحميل صفحة العلاج الإسعافي', 'error')
        return redirect(url_for('emergency.emergency_visits'))

@emergency_bp.route('/emergency-visits/<int:visit_id>/complete', methods=['POST'])
@login_required
def complete_visit(visit_id):
    if current_user.role not in ['emergency', 'admin', 'manager']:
        return jsonify({'success': False, 'message': 'غير مصرح'}), 403
    try:
        visit = db.session.get(Visit, visit_id)
        if not visit:
            return jsonify({'success': False, 'message': 'الزيارة غير موجودة'}), 404
        emergency_case = EmergencyCase.query.filter_by(visit_id=visit_id).first()
        if emergency_case:
            emergency_case.status = EmergencyStatus.COMPLETED
            emergency_case.completed_at = datetime.now(timezone.utc)
        # تسجيل اكتمال العلاج للطوارئ دون تعديل حالة الزيارة مباشرة، وإخطار الاستقبال
        visit.completed_at = datetime.now(timezone.utc)
        visit.completed_by = current_user.id
        try:
            from services.notification_service import NotificationService
            NotificationService.send_notification(
                recipient_role='reception',
                recipient_department_id=visit.department_id,
                title='إنهاء علاج زيارة طوارئ',
                message=f"تم إنهاء علاج زيارة الطوارئ رقم {visit.id} - يرجى إتمام الإجراءات",
                notification_type='warning',
                sender_id=current_user.id
            )
        except Exception as e:

            logging.warning(f"Error in {__name__}: {e}")
        db.session.commit()
        return jsonify({'success': True}), 200
    except Exception as e:
        logging.error(f"Complete emergency visit error: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'message': 'تعذر إنهاء الزيارة حالياً'}), 500