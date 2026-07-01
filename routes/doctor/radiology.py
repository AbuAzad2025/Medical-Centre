"""radiology routes - extracted from monolithic doctor.py"""

from routes.doctor import doctor_bp

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for, current_app, g
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
from app.shared.enums import VisitState
from sqlalchemy import and_, or_, desc, func, case
import logging, json, secrets
from datetime import datetime, date, timedelta, timezone


# =============================================
# RADIOLOGY ROUTES
# =============================================

@doctor_bp.route('/radiology-request/<int:visit_id>', methods=['GET', 'POST'])
@login_required
@role_required('doctor', 'admin', 'manager')
def radiology_request(visit_id):
    try:
        if 'radiology' not in getattr(g, 'enabled_modules', set()):
            flash('وحدة الأشعة غير مفعلة لهذه المنشأة', 'error')
            return redirect(url_for('doctor.patient_queue'))
        visit = Visit.query.filter(Visit.id == visit_id, Visit.tenant_id == g.tenant_id, Visit.doctor_id == current_user.id).first_or_404()
        if visit.status != VisitState.IN_PROGRESS:
            flash('لا يمكن طلب تصوير أشعة إلا أثناء سير العلاج', 'warning')
            return redirect(url_for('doctor.patient_details', visit_id=visit_id))
        if request.method == 'POST':
            test_name = request.form.get('test_name') or ''
            notes = request.form.get('notes') or request.form.get('test_description') or ''
            modality = (request.form.get('modality') or '').strip()
            body_part = (request.form.get('body_part') or '').strip()
            memo_parts = []
            if test_name:
                memo_parts.append(f"نوع التصوير: {test_name}")
            if modality:
                memo_parts.append(f"المنظار/الآلية: {modality}")
            if body_part:
                memo_parts.append(f"المنطقة: {body_part}")
            if notes:
                memo_parts.append(f"الوصف: {notes}")
            memo_text = "[مذكرة تصوير]\n" + ("\n".join(memo_parts) if memo_parts else "يرجى إجراء التصوير لدى مركز مناسب.")

            # P2-003: Create structured RadiologyRequest when modality/body_part supplied.
            structured_ok = False
            if modality or body_part:
                from services.radiology_service import radiology_service
                ok, result = radiology_service.create_request(
                    visit_id=visit.id,
                    requested_by=current_user.id,
                    modality=modality,
                    body_part=body_part,
                    notes=notes,
                    tenant_id=getattr(current_user, 'tenant_id', None),
                )
                if ok:
                    structured_ok = True
                    memo_parts.append(f"رقم الطلب المهيكل: {result['request_number']}")
                else:
                    flash(f"تعذر إنشاء طلب الأشعة المهيكل: {result.get('error')}", 'warning')

            visit.notes = (visit.notes or '')
            visit.notes += (('\n\n' if visit.notes else '') + memo_text)
            visit.radiology_ordered = True
            db.session.commit()
            try:
                db.session.add(AuditTrail(
                    entity_type='radiology_test',
                    entity_id=visit.id,
                    action='create',
                    user_id=current_user.id,
                    user_ip=request.remote_addr,
                    user_agent=request.headers.get('User-Agent'),
                    description='إضافة مذكرة تصوير' + (' + RadiologyRequest' if structured_ok else '')
                ))
                db.session.commit()
            except Exception as e:

                logging.warning(f"Error in {__name__}: {e}")
            flash('تم تدوين مذكرة التصوير. ' + ('تم إنشاء طلب أشعة مهيكل.' if structured_ok else 'يتوجه المريض للاستقبال لإنشاء زيارة لقسم الأشعة عند رغبة التنفيذ داخل المركز.'), 'info')
            return redirect(url_for('doctor.patient_details', visit_id=visit_id))
        return redirect(url_for('doctor.patient_details', visit_id=visit_id))
    except Exception as e:
        logging.error(f"Error in radiology_request: {str(e)}")
        flash('حدث خطأ أثناء إنشاء طلب الأشعة', 'error')
        return redirect(url_for('doctor.patient_details', visit_id=visit_id))

@doctor_bp.route('/radiology-results/<int:patient_id>')
@login_required
@role_required('doctor', 'admin', 'manager')
def radiology_results(patient_id):
    """عرض نتائج الأشعة للطبيب — للإطلاع فقط"""
    try:
        patient = Patient.query.filter(Patient.id == patient_id, Patient.tenant_id == g.tenant_id).first_or_404()

        rad_requests = RadiologyRequest.query.filter(
            RadiologyRequest.patient_id == patient_id
        ).order_by(desc(RadiologyRequest.created_at)).all()

        results = []
        for req in rad_requests:
            try:
                from models.radiology_result import RadiologyResult
                req_results = RadiologyResult.query.filter(
                    RadiologyResult.request_id == req.id
                ).order_by(desc(RadiologyResult.created_at)).all()
                for r in req_results:
                    results.append({
                        'modality': getattr(req, 'modality', 'غير محدد'),
                        'body_part': getattr(req, 'body_part', 'غير محدد'),
                        'findings': getattr(r, 'findings', None),
                        'impression': getattr(r, 'impression', None),
                        'status': getattr(r, 'status', 'PENDING'),
                        'is_critical': getattr(r, 'is_critical', False),
                        'recorded_at': getattr(r, 'created_at', None),
                        'radiologist': getattr(r, 'recorded_by', None)
                    })
            except Exception as e:

                logging.warning(f"Error in {__name__}: {e}")
        return render_template('doctor/radiology_results.html',
                             patient=patient,
                             rad_requests=rad_requests,
                             results=results)
    except Exception as e:
        logging.error(f"Error loading radiology results: {str(e)}")
        flash('حدث خطأ في تحميل نتائج الأشعة', 'error')
        return redirect(url_for('doctor.patient_queue'))

@doctor_bp.route('/radiology-requests')
@login_required
def radiology_requests():
    flash('تم فصل طلبات الأشعة عن الطبيب. للاستعلام، يرجى مراجعة قسم الأشعة أو الاستقبال.', 'warning')
    return redirect(url_for('doctor.patient_queue'))