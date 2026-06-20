"""lab routes - extracted from monolithic doctor.py"""

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
# LAB ROUTES
# =============================================

@doctor_bp.route('/lab-request/<int:visit_id>', methods=['GET', 'POST'])
@login_required
@role_required('doctor', 'admin', 'manager')
def lab_request(visit_id):
    try:
        visit = db.session.get(Visit, visit_id)
        if not visit or visit.doctor_id != current_user.id:
            flash('الزيارة غير موجودة أو ليس لديك صلاحية', 'error')
            return redirect(url_for('doctor.patient_queue'))
        if visit.status != 'IN_PROGRESS':
            flash('لا يمكن طلب تحاليل إلا أثناء سير العلاج', 'warning')
            return redirect(url_for('doctor.patient_details', visit_id=visit_id))
        if request.method == 'POST':
            notes = request.form.get('notes') or request.form.get('test_description') or ''
            memo_parts = []
            test_name = (request.form.get('test_name') or '').strip()
            urgency = (request.form.get('urgency') or '').strip()
            if test_name:
                memo_parts.append(f"الفحص: {test_name}")
            if notes:
                memo_parts.append(f"الوصف: {notes}")
            if urgency:
                memo_parts.append(f"الأولوية: {urgency}")
            memo_text = "[مذكرة تحاليل]\n" + ("\n".join(memo_parts) if memo_parts else "يرجى إجراء التحليل لدى مركز مناسب.")
            visit.notes = (visit.notes or '')
            visit.notes += (('\n\n' if visit.notes else '') + memo_text)
            visit.lab_tests_ordered = True
            db.session.commit()
            try:
                db.session.add(AuditTrail(
                    entity_type='lab_test',
                    entity_id=visit.id,
                    action='create',
                    user_id=current_user.id,
                    user_ip=request.remote_addr,
                    user_agent=request.headers.get('User-Agent'),
                    description='إضافة مذكرة تحاليل'
                ))
                db.session.commit()
            except Exception:

                logging.warning(f"Error in {__name__}: {e}")
            flash('تم تدوين مذكرة التحاليل. يتوجه المريض للاستقبال لإنشاء زيارة للمختبر عند رغبة التنفيذ داخل المركز.', 'info')
            return redirect(url_for('doctor.patient_details', visit_id=visit_id))
        return redirect(url_for('doctor.patient_details', visit_id=visit_id))
    except Exception as e:
        logging.error(f"Error in lab_request: {str(e)}")
        flash('حدث خطأ أثناء إنشاء طلب المختبر', 'error')
        return redirect(url_for('doctor.patient_details', visit_id=visit_id))

@doctor_bp.route('/lab-results/<int:patient_id>')
@login_required
@role_required('doctor', 'admin', 'manager')
def lab_results(patient_id):
    """عرض نتائج المختبر للطبيب — للإطلاع فقط"""
    try:
        patient = db.session.get(Patient, patient_id)
        if not patient:
            flash('المريض غير موجود', 'error')
            return redirect(url_for('doctor.patient_queue'))

        lab_requests = LabRequest.query.filter(
            LabRequest.patient_id == patient_id
        ).order_by(desc(LabRequest.created_at)).all()

        results = []
        for req in lab_requests:
            try:
                from models.lab_request import LabResult
                req_results = LabResult.query.filter(
                    LabResult.request_id == req.id
                ).order_by(desc(LabResult.created_at)).all()
                for r in req_results:
                    results.append({
                        'test_name': getattr(r, 'test_name', None) or getattr(req, 'test_name', 'غير محدد'),
                        'value': getattr(r, 'value', None),
                        'unit': getattr(r, 'unit', None),
                        'reference_range': getattr(r, 'reference_range', None),
                        'status': getattr(r, 'status', 'PENDING'),
                        'is_critical': getattr(r, 'is_critical', False),
                        'recorded_at': getattr(r, 'created_at', None),
                        'technician': getattr(r, 'recorded_by', None)
                    })
            except Exception:

                logging.warning(f"Error in {__name__}: {e}")
        return render_template('doctor/lab_results.html',
                             patient=patient,
                             lab_requests=lab_requests,
                             results=results)
    except Exception as e:
        logging.error(f"Error loading lab results: {str(e)}")
        flash('حدث خطأ في تحميل نتائج المختبر', 'error')
        return redirect(url_for('doctor.patient_queue'))

@doctor_bp.route('/lab-requests')
@login_required
def lab_requests():
    flash('تم فصل طلبات المختبر عن الطبيب. للاستعلام، يرجى مراجعة قسم المختبر أو الاستقبال.', 'warning')
    return redirect(url_for('doctor.patient_queue'))
