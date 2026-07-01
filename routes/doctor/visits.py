"""visits routes - extracted from monolithic doctor.py"""

from routes.doctor import doctor_bp, _sync_follow_up_request_for_visit
from routes.doctor.diagnosis import evaluate_clinical_rules, get_standardized_pathways, get_data_based_recommendations

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
from app.shared.enums import VisitState, QueueState, LabResultStatus
from services.visit_state_machine_service import VisitStateMachineService
from sqlalchemy import and_, or_, desc, func, case
import logging, json, secrets
from datetime import datetime, date, timedelta, timezone


# =============================================
# VISITS ROUTES
# =============================================

@doctor_bp.route('/start-treatment/<int:visit_id>', methods=['POST'])
@login_required
@role_required('doctor', 'admin', 'manager')
def start_treatment(visit_id):
    """بدء علاج المريض"""


    try:
        visit = Visit.query.filter(Visit.id == visit_id, Visit.tenant_id == g.tenant_id, Visit.doctor_id == current_user.id).first_or_404()
        if visit.status != VisitState.OPEN:
            flash('لا يمكن بدء العلاج إلا إذا كانت الزيارة في حالة انتظار', 'warning')
            return redirect(url_for('doctor.patient_queue'))
        # ضمان تحديد القسم للزيارة
        dep_id = visit.department_id
        if not dep_id:
            try:
                dep_id = current_user.department_id or None
                if not dep_id:
                    from models.department import Department
                    d = Department.query.filter_by(is_active=True).order_by(Department.id.asc()).first()
                    dep_id = d.id if d else None
                if dep_id:
                    visit.department_id = dep_id
                    db.session.commit()
                else:
                    flash('لا يمكن بدء العلاج لأن القسم غير محدد', 'error')
                    return redirect(url_for('doctor.patient_queue'))
            except Exception:
                flash('خطأ في تحديد القسم للزيارة', 'error')
                return redirect(url_for('doctor.patient_queue'))
        from models.queue_management import QueueManagement
        from services.queue_management_service import QueueManagementService
        ticket = QueueManagement.query.filter_by(
            visit_id=visit_id,
            department_id=dep_id
        ).order_by(desc(QueueManagement.called_at), QueueManagement.queued_at.asc()).first()
        if not ticket:
            flash('لا يمكن بدء العلاج قبل إدراج الزيارة في طابور القسم عبر الاستقبال', 'warning')
            return redirect(url_for('doctor.patient_queue'))
        ok, msg = QueueManagementService().start_treatment(ticket.id, started_by=current_user.id)
        if not ok:
            flash(msg, 'warning')
            return redirect(url_for('doctor.patient_queue'))
        medical_record = MedicalRecord(
            patient_id=visit.patient_id,
            title='بدء العلاج',
            details=f"تم بدء العلاج من قبل الطبيب: {current_user.full_name}",
            created_by=current_user.id
        )
        db.session.add(medical_record)
        try:
            db.session.add(AuditTrail(
                entity_type='visit',
                entity_id=visit_id,
                action='update',
                user_id=current_user.id,
                user_ip=request.remote_addr,
                user_agent=request.headers.get('User-Agent'),
                description='بدء علاج المريض'
            ))
        except Exception as e:

            logging.warning(f"Error in {__name__}: {e}")
        try:
            from services.notification_service import NotificationService
            NotificationService.send_notification(
                recipient_role='reception',
                recipient_department_id=visit.department_id,
                title='بدء علاج المريض',
                message=f"زيارة رقم {visit.id} للمريض تم بدء علاجها من قبل الطبيب",
                notification_type='info',
                sender_id=current_user.id
            )
        except Exception as e:

            logging.warning(f"Error in {__name__}: {e}")
        db.session.commit()
        flash('تم تسجيل بدء العلاج وإخطار الاستقبال', 'success')
        return redirect(url_for('doctor.patient_details', visit_id=visit_id))
    except Exception as e:
        logging.error(f"Error starting treatment: {str(e)}")
        flash('حدث خطأ في بدء العلاج', 'error')
        return redirect(url_for('doctor.patient_queue'))

def _get_patient_allergies(patient_id):
    try:
        from models.patient import PatientAllergy
        return PatientAllergy.query.filter_by(patient_id=patient_id).all()
    except Exception:
        return []

def _get_patient_medical_records(patient_id):
    try:
        return MedicalRecord.query.filter(MedicalRecord.patient_id == patient_id).order_by(desc(MedicalRecord.created_at)).limit(10).all()
    except Exception:
        return []

def _get_patient_prescriptions(patient_id):
    try:
        return Prescription.query.filter(Prescription.patient_id == patient_id).order_by(desc(Prescription.created_at)).limit(5).all()
    except Exception:
        return []

def _get_recent_other_visits(patient_id, exclude_id):
    try:
        return Visit.query.filter(Visit.patient_id == patient_id, Visit.id != exclude_id).order_by(Visit.visit_date.desc(), Visit.created_at.desc()).limit(3).all()
    except Exception:
        return []

def _parse_visit_vital_signs(visit):
    from ast import literal_eval
    raw = getattr(visit, 'vital_signs', None)
    if not raw:
        return {}
    try:
        parsed = literal_eval(raw)
        if isinstance(parsed, dict):
            return {k: parsed.get(k) for k in ('blood_pressure', 'heart_rate', 'temperature', 'respiratory_rate')}
    except Exception as e:

        logging.warning(f"Error in {__name__}: {e}")
    return {}

def _get_nurse_vital_signs(patient_id):
    try:
        from models.nurse import VitalSigns
        latest = VitalSigns.query.filter_by(patient_id=patient_id).order_by(desc(VitalSigns.recorded_at)).first()
        if latest:
            bp = None
            if latest.blood_pressure_systolic is not None or latest.blood_pressure_diastolic is not None:
                bp = f"{latest.blood_pressure_systolic or ''}/{latest.blood_pressure_diastolic or ''}".strip('/')
            return ({
                'blood_pressure': bp or None, 'heart_rate': latest.heart_rate,
                'temperature': latest.temperature, 'respiratory_rate': latest.respiratory_rate,
                'oxygen_saturation': latest.oxygen_saturation, 'weight': latest.weight,
                'height': latest.height, 'notes': latest.notes,
            }, latest.recorded_at)
    except Exception as e:

        logging.warning(f"Error in {__name__}: {e}")
    return (None, None)

def _get_visit_lab_data(visit_id):
    try:
        from models.lab_request import LabRequest, LabResult
        lab_requests = LabRequest.query.filter(LabRequest.visit_id == visit_id).order_by(desc(LabRequest.created_at)).all()
        req_ids = [r.id for r in (lab_requests or []) if getattr(r, 'id', None)]
        critical = 0
        if req_ids:
            critical = LabResult.query.filter(LabResult.request_id.in_(req_ids), LabResult.is_critical == True, LabResult.status == LabResultStatus.VALIDATED).count()
        return lab_requests, critical
    except Exception:
        return [], 0

def _get_visit_radiology_data(visit_id):
    try:
        from models.radiology_request import RadiologyRequest
        radiology_requests = RadiologyRequest.query.filter(RadiologyRequest.visit_id == visit_id).order_by(desc(RadiologyRequest.created_at)).all()
        req_ids = [r.id for r in (radiology_requests or []) if getattr(r, 'id', None)]
        critical = 0
        if req_ids:
            from models.radiology_result import RadiologyResult
            critical = RadiologyResult.query.filter(RadiologyResult.request_id.in_(req_ids), RadiologyResult.is_critical == True, RadiologyResult.status == LabResultStatus.VALIDATED).count()
        return radiology_requests, critical
    except Exception:
        return [], 0

def _count_visit_notes(visit):
    notes = visit.notes or ''
    note_count = 0
    lab_notes_count = 0
    radiology_notes_count = 0
    general_notes_count = 0
    try:
        if notes:
            note_count = notes.count('\n[') + 1
            lab_notes_count = notes.count('[مذكرة تحاليل]')
            radiology_notes_count = notes.count('[مذكرة تصوير]')
            general_notes_count = notes.count('[مذكرة عامة]') + notes.count('[ملاحظات طبية]')
    except Exception as e:

        logging.warning(f"Error in {__name__}: {e}")
    return note_count, lab_notes_count, radiology_notes_count, general_notes_count

def _get_current_prescriptions(visit_id):
    try:
        return Prescription.query.filter(Prescription.visit_id == visit_id).order_by(desc(Prescription.created_at)).limit(5).all()
    except Exception:
        return []


@doctor_bp.route('/patient-details/<int:visit_id>')
@login_required
@role_required('doctor', 'manager')
def patient_details(visit_id):
    """تفاصيل المريض والزيارة للطبيب"""
    
    
    try:
        from ast import literal_eval
        visit = Visit.query.filter(Visit.id == visit_id, Visit.tenant_id == g.tenant_id, Visit.doctor_id == current_user.id).first_or_404()
        
        medical_records = _get_patient_medical_records(visit.patient_id)
        previous_prescriptions = _get_patient_prescriptions(visit.patient_id)
        recent_visits = _get_recent_other_visits(visit.patient_id, visit.id)

        structured_vital_signs = _parse_visit_vital_signs(visit)
        nurse_latest_vital_signs, nurse_latest_vital_signs_recorded_at = _get_nurse_vital_signs(visit.patient_id)
        
        try:
            from models.lab_request import LabRequest
            lab_requests = LabRequest.query.filter(
                LabRequest.visit_id == visit_id
            ).order_by(desc(LabRequest.created_at)).all()
        except Exception:
            lab_requests = []
        critical_lab_results_count = 0
        try:
            from models.lab_request import LabResult
            req_ids = [r.id for r in (lab_requests or []) if getattr(r, 'id', None)]
            if req_ids:
                critical_lab_results_count = LabResult.query.filter(
                    LabResult.request_id.in_(req_ids),
                    LabResult.is_critical == True,
                    LabResult.status == LabResultStatus.VALIDATED
                ).count()
        except Exception:
            critical_lab_results_count = 0
        try:
            from models.radiology_request import RadiologyRequest
            radiology_requests = RadiologyRequest.query.filter(
                RadiologyRequest.visit_id == visit_id
            ).order_by(desc(RadiologyRequest.created_at)).all()
        except Exception:
            radiology_requests = []
        critical_radiology_results_count = 0
        try:
            from models.radiology_result import RadiologyResult
            req_ids = [r.id for r in (radiology_requests or []) if getattr(r, 'id', None)]
            if req_ids:
                critical_radiology_results_count = RadiologyResult.query.filter(
                    RadiologyResult.request_id.in_(req_ids),
                    RadiologyResult.is_critical == True,
                    RadiologyResult.status == LabResultStatus.VALIDATED
                ).count()
        except Exception:
            critical_radiology_results_count = 0
        note_count = 0
        if visit.notes:
            try:
                note_count = visit.notes.count('\n[') + 1
            except Exception:
                note_count = 1
        
        lab_requests_count = len(lab_requests or [])
        radiology_requests_count = len(radiology_requests or [])
        lab_notes_count = 0
        radiology_notes_count = 0
        general_notes_count = 0
        if visit.notes:
            try:
                lab_notes_count = visit.notes.count('[مذكرة تحاليل]')
                radiology_notes_count = visit.notes.count('[مذكرة تصوير]')
                general_notes_count = visit.notes.count('[مذكرة عامة]') + visit.notes.count('[ملاحظات طبية]')
            except Exception as e:

                logging.warning(f"Error in {__name__}: {e}")
        current_prescriptions = []
        try:
            current_prescriptions = Prescription.query.filter(
                Prescription.visit_id == visit_id
            ).order_by(desc(Prescription.created_at)).limit(5).all()
        except Exception:
            current_prescriptions = []

        clinical_warnings = evaluate_clinical_rules(visit, current_prescriptions, structured_vital_signs)
        standardized_pathways = get_standardized_pathways(visit.diagnosis)
        data_recommendations = get_data_based_recommendations(visit.diagnosis)
        
        return render_template('doctor/patient_details.html',
                             visit=visit,
                             medical_records=medical_records,
                             previous_prescriptions=previous_prescriptions,
                             recent_visits=recent_visits,
                             structured_vital_signs=structured_vital_signs,
                             nurse_latest_vital_signs=nurse_latest_vital_signs,
                             nurse_latest_vital_signs_recorded_at=nurse_latest_vital_signs_recorded_at,
                             lab_requests=lab_requests,
                             critical_lab_results_count=critical_lab_results_count,
                             radiology_requests=radiology_requests,
                             critical_radiology_results_count=critical_radiology_results_count,
                             note_count=note_count,
                             lab_requests_count=lab_requests_count,
                             radiology_requests_count=radiology_requests_count,
                             lab_notes_count=lab_notes_count,
                             radiology_notes_count=radiology_notes_count,
                             general_notes_count=general_notes_count,
                             patient_allergies=_get_patient_allergies(visit.patient_id),
                             clinical_warnings=clinical_warnings,
                             standardized_pathways=standardized_pathways,
                             data_recommendations=data_recommendations)
    except Exception as e:
        logging.error(f"Error loading patient details: {str(e)}")
        flash('حدث خطأ في تحميل تفاصيل المريض', 'error')
        return redirect(url_for('doctor.patient_queue'))

@doctor_bp.route('/view_patient/<int:visit_id>')
@login_required
@role_required('doctor', 'admin', 'manager')
def view_patient(visit_id):
    return redirect(url_for('doctor.patient_details', visit_id=visit_id))

@doctor_bp.route('/visit-summary/<int:visit_id>')
@login_required
@role_required('doctor', 'admin', 'manager')
def visit_summary(visit_id):
    """ملخص الزيارة"""
    
    try:
        visit = Visit.query.filter(Visit.id == visit_id, Visit.tenant_id == g.tenant_id, Visit.doctor_id == current_user.id).first_or_404()
        
        return render_template('doctor/visit_summary.html', visit=visit)
    except Exception as e:
        logging.error(f"Error in visit summary: {str(e)}")
        flash('حدث خطأ في عرض ملخص الزيارة', 'error')
        return redirect(url_for('doctor.patient_queue'))

@doctor_bp.route('/save-visit-summary/<int:visit_id>', methods=['POST'])
@login_required
@role_required('doctor', 'admin', 'manager')
def save_visit_summary(visit_id):
    """حفظ ملخص الزيارة (تشخيص، خطة علاج، متابعة)"""
    try:
        visit = Visit.query.filter(Visit.id == visit_id, Visit.tenant_id == g.tenant_id, Visit.doctor_id == current_user.id).first_or_404()
        if visit.status not in ['IN_PROGRESS', 'COMPLETED']:
            return jsonify({'success': False, 'message': 'الحالة الحالية لا تسمح بحفظ الملخص'}), 400

        # يدعم JSON أو form
        data = {}
        if request.is_json:
            data = request.get_json() or {}
        else:
            for k in ['chief_complaint','history_of_present_illness','physical_examination','vital_signs','diagnosis','treatment_plan','recommendations','follow_up_date','follow_up_notes']:
                data[k] = request.form.get(k)

        # تحديث الحقول الأساسية
        diag = (data.get('diagnosis') or '').strip() or None
        treat = (data.get('treatment_plan') or data.get('treatment') or '').strip() or None
        visit.diagnosis = diag
        visit.treatment_plan = treat

        # الشكوى/الأعراض
        cc = (data.get('chief_complaint') or '').strip()
        if cc:
            visit.symptoms = cc

        # تجميع ملاحظات نصية إضافية
        extra_notes_parts = []
        for key,label in [
            ('history_of_present_illness','تاريخ المرض الحالي'),
            ('physical_examination','الفحص السريري'),
            ('vital_signs','العلامات الحيوية'),
            ('recommendations','التوصيات'),
            ('follow_up_notes','ملاحظات المتابعة')
        ]:
            val = (data.get(key) or '').strip()
            if val:
                extra_notes_parts.append(f"[{label}]\n{val}")
        if extra_notes_parts:
            if not visit.notes:
                visit.notes = ''
            visit.notes += ('\n\n' if visit.notes else '') + '\n\n'.join(extra_notes_parts)

        # متابعة
        fup_raw = (data.get('follow_up_date') or '').strip()
        if fup_raw:
            try:
                from datetime import datetime as _dt
                visit.follow_up_date = _dt.strptime(fup_raw, '%Y-%m-%d').date()
                visit.follow_up_required = True
            except Exception as e:

                logging.warning(f"Error in {__name__}: {e}")
        try:
            _sync_follow_up_request_for_visit(visit, current_user.id)
        except Exception as e:

            logging.warning(f"Error in {__name__}: {e}")
        db.session.commit()
        try:
            db.session.add(AuditTrail(
                entity_type='visit',
                entity_id=visit_id,
                action='update',
                user_id=current_user.id,
                user_ip=request.remote_addr,
                user_agent=request.headers.get('User-Agent'),
                description='حفظ ملخص الزيارة'
            ))
            db.session.commit()
        except Exception as e:

            logging.warning(f"Error in {__name__}: {e}")
        return jsonify({'success': True})
    except Exception as e:
        logging.error(f"Error saving visit summary: {str(e)}")
        return jsonify({'success': False, 'message': 'فشل حفظ ملخص الزيارة'}), 500

@doctor_bp.route('/end-treatment/<int:visit_id>', methods=['POST'])
@login_required
@role_required('doctor', 'admin', 'manager')
def end_treatment(visit_id):
    """إنهاء العلاج"""
    
    try:
        visit = Visit.query.filter(Visit.id == visit_id, Visit.tenant_id == g.tenant_id, Visit.doctor_id == current_user.id).first_or_404()
        if visit.status != VisitState.IN_PROGRESS:
            flash('لا يمكن إنهاء العلاج إلا أثناء سير العلاج', 'warning')
            return redirect(url_for('doctor.patient_queue'))
        from models.queue_management import QueueManagement
        from services.queue_management_service import QueueManagementService
        ticket = QueueManagement.query.filter_by(
            visit_id=visit_id,
            department_id=visit.department_id
        ).filter(QueueManagement.status == QueueState.IN_PROGRESS).order_by(desc(QueueManagement.started_at)).first()
        if ticket:
            ok, msg = QueueManagementService().complete_treatment(ticket.id, completed_by=current_user.id)
            if not ok:
                flash(msg, 'warning')
                return redirect(url_for('doctor.patient_queue'))
        VisitStateMachineService.transition(
            visit, VisitState.COMPLETED, actor=current_user
        )
        visit.completed_by = current_user.id
        from datetime import timezone
        visit.completed_at = datetime.now(timezone.utc)
        medical_record = MedicalRecord(
            patient_id=visit.patient_id,
            title='إنهاء العلاج',
            details=f"تم إنهاء العلاج بنجاح من قبل الطبيب: {current_user.full_name}",
            created_by=current_user.id
        )
        
        db.session.add(medical_record)
        
        # إرسال إشعار للاستقبال لإتمام إجراءات إنهاء الزيارة/الأرشفة
        try:
            from services.notification_service import NotificationService
            NotificationService.send_notification(
                recipient_role='reception',
                recipient_department_id=visit.department_id,
                title='إنهاء علاج المريض',
                message=f"زيارة رقم {visit.id} للمريض تم إنهاء علاجها - يرجى إتمام الإجراءات", 
                notification_type='warning',
                sender_id=current_user.id
            )
        except Exception as e:

            logging.warning(f"Error in {__name__}: {e}")
        db.session.commit()
        try:
            db.session.add(AuditTrail(
                entity_type='visit',
                entity_id=visit_id,
                action='update',
                user_id=current_user.id,
                user_ip=request.remote_addr,
                user_agent=request.headers.get('User-Agent'),
                description='إنهاء العلاج',
                new_values=json.dumps({'status': 'COMPLETED'})
            ))
            db.session.commit()
        except Exception as e:

            logging.warning(f"Error in {__name__}: {e}")
        flash('تم تسجيل إنهاء العلاج وإخطار الاستقبال', 'success')
        return redirect(url_for('doctor.patient_queue'))
    except Exception as e:
        logging.error(f"Error ending treatment: {str(e)}", exc_info=True)
        flash('حدث خطأ في إنهاء العلاج', 'error')
        return redirect(url_for('doctor.patient_queue'))

# مسارات إضافية للطبيب الاحترافي

@doctor_bp.route('/visits')
@login_required
@role_required('doctor', 'admin', 'manager')
def visits():
    """قائمة الزيارات — تُحوِّل لطابور المرضى لاختيار زيارة (لا قالب تفاصيل بلا بيانات)."""
    return redirect(url_for('doctor.patient_queue'))