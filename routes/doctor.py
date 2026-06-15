 

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, current_app
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
from app_factory import db
import logging
import json
from datetime import datetime, date, timedelta, timezone
from sqlalchemy import and_, or_, desc, func, case
import secrets

from models.system_config import SystemConfig

doctor_bp = Blueprint('doctor', __name__)

@doctor_bp.route('/')
@login_required
def index():
    return redirect(url_for('doctor.dashboard'))

def _doctor_note_templates_cfg():
    return SystemConfig.query.filter_by(config_key='doctor_note_templates').first()

def _default_doctor_note_templates():
    return [
        {'id': secrets.token_hex(8), 'name': 'SOAP قالب', 'text': 'S:\nO:\nA:\nP:\n', 'is_active': True},
        {'id': secrets.token_hex(8), 'name': 'تعليمات خروج', 'text': 'تعليمات للمريض:\n- \n- \n', 'is_active': True},
        {'id': secrets.token_hex(8), 'name': 'متابعة', 'text': 'يوصى بالمتابعة خلال ____ أيام.\nعلامات إنذار: ________\n', 'is_active': True},
    ]

def _get_doctor_note_templates():
    cfg = _doctor_note_templates_cfg()
    if not cfg:
        cfg = SystemConfig(
            config_key='doctor_note_templates',
            config_type='json',
            config_value='[]',
            category='general',
            description='قوالب ملاحظات الطبيب',
            is_system=False,
            is_encrypted=False,
            created_by=getattr(current_user, 'id', None),
            updated_by=getattr(current_user, 'id', None),
        )
        db.session.add(cfg)
        templates = _default_doctor_note_templates()
        cfg.set_value(templates)
        db.session.commit()
        return templates

    templates = cfg.get_value() if cfg.config_type == 'json' else []
    if not isinstance(templates, list):
        templates = []
    if not templates:
        templates = _default_doctor_note_templates()
        cfg.set_value(templates)
        cfg.updated_by = getattr(current_user, 'id', None)
        db.session.commit()
    return templates

def _save_doctor_note_templates(templates):
    cfg = _doctor_note_templates_cfg()
    if not cfg:
        cfg = SystemConfig(
            config_key='doctor_note_templates',
            config_type='json',
            config_value='[]',
            category='general',
            description='قوالب ملاحظات الطبيب',
            is_system=False,
            is_encrypted=False,
            created_by=getattr(current_user, 'id', None),
            updated_by=getattr(current_user, 'id', None),
        )
        db.session.add(cfg)
    if not isinstance(templates, list):
        templates = []
    cfg.config_type = 'json'
    cfg.set_value(templates)
    cfg.updated_by = getattr(current_user, 'id', None)
    db.session.commit()

def _doctor_dashboard_layout_cfg_key():
    return f'doctor_dashboard_layout_{current_user.id}'

def _default_doctor_dashboard_layout():
    return [
        {'id': 'stats_overview', 'title': 'الإحصائيات السريعة', 'order': 1, 'enabled': True},
        {'id': 'patients_actions', 'title': 'المرضى والإجراءات', 'order': 2, 'enabled': True},
        {'id': 'smart_insights', 'title': 'الدعم الذكي والتحليلات', 'order': 3, 'enabled': True}
    ]

def _get_doctor_dashboard_layout():
    cfg = SystemConfig.query.filter_by(config_key=_doctor_dashboard_layout_cfg_key()).first()
    if not cfg:
        cfg = SystemConfig(
            config_key=_doctor_dashboard_layout_cfg_key(),
            config_type='json',
            config_value='[]',
            category='doctor',
            description='تخصيص لوحة الطبيب',
            is_system=False,
            is_encrypted=False,
            created_by=getattr(current_user, 'id', None),
            updated_by=getattr(current_user, 'id', None),
        )
        db.session.add(cfg)
        layout = _default_doctor_dashboard_layout()
        cfg.set_value(layout)
        db.session.commit()
        return layout
    layout = cfg.get_value() if cfg.config_type == 'json' else []
    if not isinstance(layout, list) or not layout:
        layout = _default_doctor_dashboard_layout()
        cfg.config_type = 'json'
        cfg.set_value(layout)
        cfg.updated_by = getattr(current_user, 'id', None)
        db.session.commit()
    return layout

def _save_doctor_dashboard_layout(items):
    cfg = SystemConfig.query.filter_by(config_key=_doctor_dashboard_layout_cfg_key()).first()
    if not cfg:
        cfg = SystemConfig(
            config_key=_doctor_dashboard_layout_cfg_key(),
            config_type='json',
            config_value='[]',
            category='doctor',
            description='تخصيص لوحة الطبيب',
            is_system=False,
            is_encrypted=False,
            created_by=getattr(current_user, 'id', None),
            updated_by=getattr(current_user, 'id', None),
        )
        db.session.add(cfg)
    cfg.config_type = 'json'
    cfg.set_value(items)
    cfg.updated_by = getattr(current_user, 'id', None)
    db.session.commit()


def _sync_follow_up_request_for_visit(visit: Visit, actor_user_id: int):
    suggested = getattr(visit, 'follow_up_date', None)
    required = bool(getattr(visit, 'follow_up_required', False))
    if required and suggested:
        existing = FollowUpRequest.query.filter_by(source_visit_id=visit.id).order_by(FollowUpRequest.created_at.desc()).first()
        if existing and existing.status in {'CANCELLED', 'DONE'}:
            existing = None
        if existing:
            existing.patient_id = visit.patient_id
            existing.doctor_id = visit.doctor_id
            existing.suggested_date = suggested
            existing.notes = getattr(visit, 'follow_up_notes', None) or existing.notes
            existing.status = existing.status if existing.status == 'SCHEDULED' else 'PENDING'
            existing.updated_at = datetime.now(timezone.utc)
        else:
            db.session.add(FollowUpRequest(
                patient_id=visit.patient_id,
                doctor_id=visit.doctor_id,
                source_visit_id=visit.id,
                suggested_date=suggested,
                notes=getattr(visit, 'follow_up_notes', None),
                status='PENDING',
                created_by=actor_user_id
            ))
        return

    existing = FollowUpRequest.query.filter_by(source_visit_id=visit.id).order_by(FollowUpRequest.created_at.desc()).first()
    if existing and existing.status in {'PENDING'}:
        existing.status = 'CANCELLED'
        existing.updated_at = datetime.now(timezone.utc)

@doctor_bp.route('/dashboard')
@login_required
@role_required('doctor', 'admin', 'manager')
def dashboard():
    """لوحة تحكم الطبيب الاحترافية"""
    
    
    try:
        # إحصائيات متقدمة للطبيب
        today = date.today()
        week_ago = today - timedelta(days=7)
        
        # الزيارات اليوم
        today_visits = Visit.query.filter(
            Visit.doctor_id == current_user.id,
            Visit.visit_date == today,
            Visit.status.in_(['OPEN', 'IN_PROGRESS'])
        ).count()
        
        # الزيارات المعلقة
        pending_visits = Visit.query.filter(
            Visit.doctor_id == current_user.id,
            Visit.status == 'OPEN'
        ).count()
        
        # الزيارات المكتملة اليوم
        completed_today = Visit.query.filter(
            Visit.doctor_id == current_user.id,
            Visit.visit_date == today,
            Visit.status == 'COMPLETED'
        ).count()
        
        # الزيارات الأسبوع الماضي
        weekly_visits = Visit.query.filter(
            Visit.doctor_id == current_user.id,
            Visit.visit_date >= week_ago,
            Visit.status == 'COMPLETED'
        ).count()
        
        # الوصفات الطبية اليوم
        prescriptions_today = Prescription.query.join(Visit).filter(
            Visit.doctor_id == current_user.id,
            Visit.visit_date == today
        ).count()
        
        # طلبات المختبر المعلقة
        pending_lab_requests = LabRequest.query.join(Visit).filter(
            Visit.doctor_id == current_user.id,
            LabRequest.status == 'REQUESTED'
        ).count()
        
        # طلبات الأشعة المعلقة
        pending_radiology_requests = RadiologyRequest.query.join(Visit).filter(
            Visit.doctor_id == current_user.id,
            RadiologyRequest.status == 'REQUESTED'
        ).count()
        
        # المرضى القادمين اليوم
        upcoming_patients = Visit.query.filter(
            Visit.doctor_id == current_user.id,
            Visit.visit_date == today,
            Visit.status.in_(['OPEN','READY'])
        ).order_by(Visit.visit_time).limit(5).all()
        
        # الإحصائيات
        stats = {
            'today_visits': today_visits,
            'pending_visits': pending_visits,
            'completed_today': completed_today,
            'weekly_visits': weekly_visits,
            'prescriptions_today': prescriptions_today,
            'pending_lab_requests': pending_lab_requests,
            'pending_radiology_requests': pending_radiology_requests
        }
        # إحصائيات مالية للطبيب تظهر فقط للأدوار الإدارية المصرح لها
        if current_user.role in ['manager', 'super_admin', 'accountant']:
            try:
                from decimal import Decimal, ROUND_HALF_UP
                from models.pricing import DoctorPricing
                completed_today_visits = Visit.query.filter(
                    Visit.doctor_id == current_user.id,
                    Visit.visit_date == today,
                    Visit.status == 'COMPLETED'
                ).all()
                def compute_fee(v):
                    total = Decimal(str(v.total_amount or 0))
                    fee = None
                    pricing = None
                    try:
                        pricing = DoctorPricing.query.filter(
                            DoctorPricing.doctor_id == v.doctor_id,
                            DoctorPricing.department_id == v.department_id,
                            DoctorPricing.is_active == True
                        ).order_by(DoctorPricing.effective_from.desc()).first()
                    except Exception:
                        pricing = None
                    vt = (v.visit_type or '').upper()
                    if pricing:
                        if vt in ['FIRST','CONSULTATION'] and pricing.consultation_price:
                            fee = Decimal(str(pricing.consultation_price))
                        elif vt in ['FOLLOW_UP'] and pricing.follow_up_price:
                            fee = Decimal(str(pricing.follow_up_price))
                        elif getattr(v, 'is_emergency', False) and pricing.emergency_price:
                            fee = Decimal(str(pricing.emergency_price))
                    if fee is None:
                        fee = (total * Decimal('0.30'))
                    if fee > total:
                        fee = total
                    return fee.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                earnings_today = sum(compute_fee(v) for v in completed_today_visits) if completed_today_visits else Decimal('0.00')
                month_start = date(today.year, today.month, 1)
                weekly_completed = Visit.query.filter(
                    Visit.doctor_id == current_user.id,
                    Visit.visit_date >= week_ago,
                    Visit.status == 'COMPLETED'
                ).all()
                monthly_completed = Visit.query.filter(
                    Visit.doctor_id == current_user.id,
                    Visit.visit_date >= month_start,
                    Visit.status == 'COMPLETED'
                ).all()
                earnings_week = sum(compute_fee(v) for v in weekly_completed) if weekly_completed else Decimal('0.00')
                earnings_month = sum(compute_fee(v) for v in monthly_completed) if monthly_completed else Decimal('0.00')
                stats['doctor_earnings_today'] = float(earnings_today)
                stats['doctor_earnings_week'] = float(earnings_week)
                stats['doctor_earnings_month'] = float(earnings_month)
            except Exception:
                stats['doctor_earnings_today'] = 0.0
                stats['doctor_earnings_week'] = 0.0
                stats['doctor_earnings_month'] = 0.0
        else:
            stats['doctor_earnings_today'] = None
            stats['doctor_earnings_week'] = None
            stats['doctor_earnings_month'] = None
        # توصيات ذكية وتحليلات الأداء
        recommendations = get_clinical_decision_support()
        analytics = get_medical_analytics()
        optimizations = get_workflow_optimization()
        stats['smart_recommendations'] = recommendations
        stats['medical_analytics'] = analytics
        stats['workflow_optimizations'] = optimizations
        
        return render_template('doctor/dashboard_new.html',
                             stats=stats,
                             upcoming_patients=upcoming_patients,
                             viewing_doctor=None)
    except Exception as e:
        logging.error(f"Error in doctor dashboard: {str(e)}")
        flash('حدث خطأ في تحميل لوحة التحكم', 'error')
        return redirect(url_for('doctor.patient_queue'))

@doctor_bp.route('/patient-queue')
@login_required
@role_required('doctor', 'admin', 'manager')
def patient_queue():
    """طابور المرضى للطبيب - إدارة متقدمة"""
    
    
    try:
        # جلب المرضى المخصصين للطبيب مع تفاصيل إضافية
        patients = Visit.query.filter(
            Visit.doctor_id == current_user.id,
            Visit.status.in_(['OPEN', 'IN_PROGRESS'])
        ).order_by(Visit.visit_time).all()
        
        # إحصائيات الطابور
        queue_stats = {
            'total_patients': len(patients),
            'ready_patients': len([p for p in patients if p.status == 'OPEN']),
            'in_progress': len([p for p in patients if p.status == 'IN_PROGRESS']),
            'average_wait_time': 15
        }
        # إمكانية البدء لكل زيارة بناءً على حالة تذكرة الطابور (يجب أن تكون 'called')
        can_start_map = {}
        try:
            from models.queue_management import QueueManagement
            for v in patients:
                can_start_map[v.id] = bool(QueueManagement.query.filter_by(
                    visit_id=v.id,
                    department_id=v.department_id,
                    status='called'
                ).first())
        except Exception:
            for v in patients:
                can_start_map[v.id] = False

        today = date.today()
        todays_visits = Visit.query.filter(
            Visit.doctor_id == current_user.id,
            Visit.visit_date == today,
            Visit.status.in_(['OPEN','IN_PROGRESS'])
        ).all()
        linked_requests = []
        for v in todays_visits:
            lab_pending = LabRequest.query.filter(
                LabRequest.visit_id == v.id,
                LabRequest.status.in_(['REQUESTED','IN_PROGRESS'])
            ).count()
            rad_pending = RadiologyRequest.query.filter(
                RadiologyRequest.visit_id == v.id,
                RadiologyRequest.status.in_(['REQUESTED','IN_PROGRESS'])
            ).count()
            linked_requests.append({
                'visit_id': v.id,
                'patient_name': getattr(v.patient, 'full_name', 'غير محدد'),
                'lab_pending': lab_pending,
                'rad_pending': rad_pending
            })
        
        flash('لزيارة قسم أو طبيب آخر، يرجى إنشاء زيارة جديدة من الاستقبال', 'info')
        return render_template('doctor/patient_queue.html', 
                             patients=patients, 
                             queue_stats=queue_stats,
                             linked_requests=linked_requests,
                             can_start_map=can_start_map)
    except Exception as e:
        logging.error(f"Error loading patient queue: {str(e)}")
        flash('حدث خطأ في تحميل طابور المرضى', 'error')
        return redirect(url_for('doctor.dashboard'))

@doctor_bp.route('/start-treatment/<int:visit_id>', methods=['POST'])
@login_required
@role_required('doctor', 'admin', 'manager')
def start_treatment(visit_id):
    """بدء علاج المريض"""


    try:
        visit = db.session.get(Visit, visit_id)
        if not visit or visit.doctor_id != current_user.id:
            flash('الزيارة غير موجودة أو ليس لديك صلاحية', 'error')
            return redirect(url_for('doctor.patient_queue'))
        if visit.status != 'OPEN':
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
        except Exception:
            pass
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
        except Exception:
            pass
        db.session.commit()
        flash('تم تسجيل بدء العلاج وإخطار الاستقبال', 'success')
        return redirect(url_for('doctor.patient_details', visit_id=visit_id))
    except Exception as e:
        logging.error(f"Error starting treatment: {str(e)}")
        flash('حدث خطأ في بدء العلاج', 'error')
        return redirect(url_for('doctor.patient_queue'))

@doctor_bp.route('/patient-details/<int:visit_id>')
@login_required
@role_required('doctor', 'manager')
def patient_details(visit_id):
    """تفاصيل المريض والزيارة للطبيب"""
    
    
    try:
        from ast import literal_eval
        visit = db.session.get(Visit, visit_id)
        if not visit or visit.doctor_id != current_user.id:
            flash('الزيارة غير موجودة أو ليس لديك صلاحية', 'error')
            return redirect(url_for('doctor.patient_queue'))
        
        # جلب السجل الطبي للمريض
        medical_records = MedicalRecord.query.filter(
            MedicalRecord.patient_id == visit.patient_id
        ).order_by(desc(MedicalRecord.created_at)).limit(10).all()
        
        # جلب الوصفات السابقة
        previous_prescriptions = Prescription.query.filter(
            Prescription.patient_id == visit.patient_id
        ).order_by(desc(Prescription.created_at)).limit(5).all()

        # جلب أحدث زيارات أخرى لنفس المريض
        recent_visits = []
        try:
            recent_visits = Visit.query.filter(
                Visit.patient_id == visit.patient_id,
                Visit.id != visit.id
            ).order_by(
                Visit.visit_date.desc(),
                Visit.created_at.desc()
            ).limit(3).all()
        except Exception:
            recent_visits = []

        # تفكيك العلامات الحيوية المخزنة كسلسلة
        structured_vital_signs = {}
        nurse_latest_vital_signs = None
        nurse_latest_vital_signs_recorded_at = None
        raw_vital_signs = getattr(visit, 'vital_signs', None)
        if raw_vital_signs:
            try:
                parsed = literal_eval(raw_vital_signs)
                if isinstance(parsed, dict):
                    structured_vital_signs = {
                        'blood_pressure': parsed.get('blood_pressure'),
                        'heart_rate': parsed.get('heart_rate'),
                        'temperature': parsed.get('temperature'),
                        'respiratory_rate': parsed.get('respiratory_rate'),
                    }
            except Exception:
                structured_vital_signs = {}

        try:
            from models.nurse import VitalSigns
            latest = VitalSigns.query.filter_by(patient_id=visit.patient_id).order_by(desc(VitalSigns.recorded_at)).first()
            if latest:
                bp = None
                if latest.blood_pressure_systolic is not None or latest.blood_pressure_diastolic is not None:
                    bp = f"{latest.blood_pressure_systolic or ''}/{latest.blood_pressure_diastolic or ''}".strip('/')
                nurse_latest_vital_signs = {
                    'blood_pressure': bp or None,
                    'heart_rate': latest.heart_rate,
                    'temperature': latest.temperature,
                    'respiratory_rate': latest.respiratory_rate,
                    'oxygen_saturation': latest.oxygen_saturation,
                    'weight': latest.weight,
                    'height': latest.height,
                    'notes': latest.notes,
                }
                nurse_latest_vital_signs_recorded_at = latest.recorded_at
        except Exception:
            nurse_latest_vital_signs = None
            nurse_latest_vital_signs_recorded_at = None
        
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
                    LabResult.status == 'VALIDATED'
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
            from models.radiology_test import RadiologyResult
            req_ids = [r.id for r in (radiology_requests or []) if getattr(r, 'id', None)]
            if req_ids:
                critical_radiology_results_count = RadiologyResult.query.filter(
                    RadiologyResult.request_id.in_(req_ids),
                    RadiologyResult.is_critical == True,
                    RadiologyResult.status == 'VALIDATED'
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
            except Exception:
                pass

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

@doctor_bp.route('/diagnosis/<int:visit_id>', methods=['GET', 'POST'])
@login_required
@role_required('doctor', 'admin', 'manager')
def diagnosis(visit_id):
    """إدخال التشخيص"""


    try:
        from ast import literal_eval
        visit = db.session.get(Visit, visit_id)
        if not visit or visit.doctor_id != current_user.id:
            flash('الزيارة غير موجودة أو ليس لديك صلاحية', 'error')
            return redirect(url_for('doctor.patient_queue'))
        if visit.status in ['COMPLETED', 'ARCHIVED']:
            flash('لا يمكن تعديل التشخيص بعد اكتمال أو أرشفة الزيارة', 'warning')
            return redirect(url_for('doctor.patient_queue'))

        if request.method == 'POST':
            # البيانات الأساسية
            chief_complaint = request.form.get('chief_complaint')
            symptoms = request.form.get('symptoms')
            diagnosis = request.form.get('diagnosis')
            differential_diagnosis = request.form.get('differential_diagnosis')
            treatment_plan = request.form.get('treatment_plan')
            follow_up_notes = request.form.get('follow_up_notes')
            follow_up_required = True if request.form.get('follow_up_required') else False
            follow_up_date_raw = (request.form.get('follow_up_date') or '').strip()
            additional_notes = (request.form.get('notes') or '').strip()
            
            # الفحص السريري
            vital_signs = {
                'blood_pressure': request.form.get('blood_pressure'),
                'heart_rate': request.form.get('heart_rate'),
                'temperature': request.form.get('temperature'),
                'respiratory_rate': request.form.get('respiratory_rate')
            }
            
            # تحديث الزيارة
            visit.chief_complaint = chief_complaint
            visit.symptoms = symptoms
            visit.diagnosis = diagnosis
            visit.differential_diagnosis = differential_diagnosis
            visit.treatment_plan = treatment_plan
            visit.follow_up_notes = follow_up_notes
            visit.follow_up_required = follow_up_required
            if follow_up_date_raw:
                try:
                    visit.follow_up_date = datetime.strptime(follow_up_date_raw, '%Y-%m-%d').date()
                except Exception:
                    visit.follow_up_date = None
            else:
                visit.follow_up_date = None
            visit.vital_signs = str(vital_signs)
            visit.status = 'IN_PROGRESS'
            if additional_notes:
                memo_text = "[ملاحظات طبية]\n" + additional_notes
                visit.notes = (visit.notes or '')
                visit.notes += (('\n\n' if visit.notes else '') + memo_text)

            try:
                _sync_follow_up_request_for_visit(visit, current_user.id)
            except Exception:
                pass
            
            # إنشاء سجل طبي
            medical_record = MedicalRecord(
                patient_id=visit.patient_id,
                title='تشخيص طبي',
                details=f"الشكوى الرئيسية: {chief_complaint}\nالأعراض: {symptoms}\nالتشخيص: {diagnosis}",
                created_by=current_user.id
            )
            
            db.session.add(medical_record)
            db.session.commit()
            try:
                db.session.add(AuditTrail(
                    entity_type='visit',
                    entity_id=visit_id,
                    action='update',
                    user_id=current_user.id,
                    user_ip=request.remote_addr,
                    user_agent=request.headers.get('User-Agent'),
                    description='حفظ التشخيص',
                    new_values=json.dumps({'diagnosis': diagnosis, 'treatment_plan': treatment_plan})
                ))
                db.session.commit()
            except Exception:
                pass

            flash('تم حفظ التشخيص بنجاح', 'success')
            return redirect(url_for('doctor.patient_details', visit_id=visit_id))

        structured_vital_signs = {}
        raw_vital_signs = getattr(visit, 'vital_signs', None)
        if raw_vital_signs:
            try:
                parsed = literal_eval(raw_vital_signs)
                if isinstance(parsed, dict):
                    structured_vital_signs = parsed
            except Exception:
                structured_vital_signs = {}
        return render_template('doctor/diagnosis.html', visit=visit, structured_vital_signs=structured_vital_signs)
    except Exception as e:
        logging.error(f"Error in diagnosis: {str(e)}")
        flash('حدث خطأ في حفظ التشخيص', 'error')
        return redirect(url_for('doctor.patient_queue'))

@doctor_bp.route('/prescription/<int:visit_id>', methods=['GET', 'POST'])
@login_required
@role_required('doctor', 'admin', 'manager')
def prescription(visit_id):
    """كتابة الوصفة الطبية"""
    
    try:
        visit = db.session.get(Visit, visit_id)
        if not visit or visit.doctor_id != current_user.id:
            flash('الزيارة غير موجودة أو ليس لديك صلاحية', 'error')
            return redirect(url_for('doctor.patient_queue'))
        if visit.status != 'IN_PROGRESS':
            flash('لا يمكن كتابة وصفة إلا أثناء سير العلاج', 'warning')
            return redirect(url_for('doctor.patient_details', visit_id=visit_id))

        from models.medication import Medication, PrescriptionItem
        from models.system_config import SystemConfig

        medications = Medication.query.filter_by(is_active=True).order_by(Medication.trade_name.asc()).limit(1000).all()

        templates_key = f'doctor_rx_templates_{current_user.id}'
        doctor_templates = []
        try:
            cfg = SystemConfig.query.filter_by(config_key=templates_key).first()
            if cfg and cfg.config_type == 'json':
                doctor_templates = cfg.get_value() or []
        except Exception:
            doctor_templates = []

        visit_prescriptions = Prescription.query.filter(
            Prescription.visit_id == visit_id
        ).order_by(desc(Prescription.created_at)).limit(10).all()

        if request.method == 'POST':
            item_med_ids = request.form.getlist('item_medication_id[]')
            item_med_refs = request.form.getlist('item_medication_ref[]')
            item_dosages = request.form.getlist('item_dosage[]')
            item_frequencies = request.form.getlist('item_frequency[]')
            item_durations = request.form.getlist('item_duration_days[]')
            item_quantities = request.form.getlist('item_quantity[]')
            item_instructions = request.form.getlist('item_instructions[]')

            if not item_med_ids and item_med_refs:
                for ref in item_med_refs:
                    ref = (ref or '').strip()
                    if '|' in ref:
                        item_med_ids.append(ref.split('|', 1)[0].strip())
                    else:
                        item_med_ids.append('')

            additional_notes = (request.form.get('additional_notes') or '').strip()
            non_catalog_medications = (request.form.get('non_catalog_medications') or '').strip()

            legacy_medication_name = (request.form.get('medication_name') or '').strip()
            legacy_dosage = (request.form.get('dosage') or '').strip()
            legacy_frequency = (request.form.get('frequency') or '').strip()
            legacy_duration = (request.form.get('duration') or '').strip()
            legacy_instructions = (request.form.get('instructions') or '').strip()

            legacy_duration_days = 0
            if legacy_duration:
                for part in legacy_duration.replace('-', ' ').replace('/', ' ').split():
                    if part.isdigit():
                        legacy_duration_days = int(part)
                        break

            any_item = any([(x or '').strip() for x in item_med_ids])
            if (not any_item) and legacy_medication_name:
                try:
                    med = Medication.query.filter(
                        db.or_(
                            Medication.trade_name.ilike(legacy_medication_name),
                            Medication.generic_name.ilike(legacy_medication_name),
                            Medication.scientific_name.ilike(legacy_medication_name)
                        )
                    ).first()
                except Exception:
                    med = None
                if med and legacy_dosage and legacy_frequency and legacy_duration_days > 0:
                    item_med_ids = [str(med.id)]
                    item_dosages = [legacy_dosage]
                    item_frequencies = [legacy_frequency]
                    item_durations = [str(legacy_duration_days)]
                    item_quantities = ['1']
                    item_instructions = [legacy_instructions]
                    any_item = True
                else:
                    legacy_line_parts = [legacy_medication_name]
                    if legacy_dosage:
                        legacy_line_parts.append(f"جرعة: {legacy_dosage}")
                    if legacy_frequency:
                        legacy_line_parts.append(f"تكرار: {legacy_frequency}")
                    if legacy_duration:
                        legacy_line_parts.append(f"المدة: {legacy_duration}")
                    if legacy_instructions:
                        legacy_line_parts.append(f"تعليمات: {legacy_instructions}")
                    legacy_line = " | ".join([x for x in legacy_line_parts if x])
                    non_catalog_medications = (non_catalog_medications + "\n" if non_catalog_medications else "") + legacy_line

            if (not any_item) and (not additional_notes) and (not non_catalog_medications):
                flash('يرجى إضافة دواء واحد على الأقل من القائمة', 'warning')
                return render_template(
                    'doctor/prescription.html',
                    visit=visit,
                    medications=medications,
                    doctor_templates=doctor_templates,
                    visit_prescriptions=visit_prescriptions
                )

            from datetime import timezone
            prescription_number = f"RX-{visit_id}-{int(datetime.now(timezone.utc).timestamp())}"
            notes_parts = []
            if additional_notes:
                notes_parts.append(additional_notes)
            if non_catalog_medications:
                notes_parts.append('أدوية غير موجودة بالمخزون:\n' + non_catalog_medications)
            notes = '\n\n'.join([p for p in notes_parts if p]) or None

            prescription = Prescription(
                visit_id=visit_id,
                patient_id=visit.patient_id,
                doctor_id=current_user.id,
                prescription_number=prescription_number,
                diagnosis=visit.diagnosis,
                notes=notes
            )
            db.session.add(prescription)
            db.session.flush()

            warnings = []
            from decimal import Decimal
            total_cost = Decimal('0')
            used_med_ids = set()
            for i in range(max(len(item_med_ids), len(item_med_refs), len(item_dosages), len(item_frequencies), len(item_durations), len(item_instructions), len(item_quantities))):
                med_id_raw = item_med_ids[i] if i < len(item_med_ids) else ''
                if not (med_id_raw or '').strip():
                    continue
                try:
                    med_id = int(str(med_id_raw).strip())
                except Exception:
                    continue

                med = db.session.get(Medication, med_id)
                if not med:
                    continue
                used_med_ids.add(med.id)

                dosage = (item_dosages[i] if i < len(item_dosages) else '').strip()
                frequency = (item_frequencies[i] if i < len(item_frequencies) else '').strip()
                duration_days_raw = (item_durations[i] if i < len(item_durations) else '').strip()
                quantity_raw = (item_quantities[i] if i < len(item_quantities) else '').strip()
                instructions = (item_instructions[i] if i < len(item_instructions) else '').strip() or None
                if not instructions:
                    instructions = (getattr(med, 'standard_instructions', None) or '').strip() or None

                if not dosage or not frequency:
                    continue

                try:
                    duration_days = int(duration_days_raw)
                except Exception:
                    duration_days = 0
                if duration_days <= 0:
                    continue

                try:
                    quantity = int(quantity_raw) if quantity_raw else 1
                except Exception:
                    quantity = 1
                if quantity <= 0:
                    quantity = 1

                stored_dosage = f"{dosage} | {frequency}" if frequency else dosage
                unit_price = med.price or 0
                total_price = unit_price * quantity
                total_cost += (total_price or 0)

                pi = PrescriptionItem(
                    prescription_id=prescription.id,
                    medication_id=med.id,
                    dosage=stored_dosage,
                    quantity=quantity,
                    duration_days=duration_days,
                    instructions=instructions,
                    unit_price=unit_price,
                    total_price=total_price
                )
                db.session.add(pi)

                try:
                    from models.patient import PatientAllergy
                    allergy_records = PatientAllergy.query.filter_by(patient_id=visit.patient_id).all()
                    med_names = [x for x in [
                        (med.trade_name or '').lower(),
                        (med.generic_name or '').lower(),
                        (med.scientific_name or '').lower()
                    ] if x]
                    for ar in allergy_records:
                        allergen = (ar.allergen or '').lower()
                        if not allergen:
                            continue
                        if any(allergen in n or n in allergen for n in med_names):
                            warnings.append(f'تحذير: حساسية مسجلة تجاه {med.trade_name}')
                            break
                except Exception:
                    pass

            try:
                med_ids_sorted = sorted({int(x) for x in used_med_ids if x})
                pairs = []
                for i in range(len(med_ids_sorted)):
                    for j in range(i + 1, len(med_ids_sorted)):
                        a = min(med_ids_sorted[i], med_ids_sorted[j])
                        b = max(med_ids_sorted[i], med_ids_sorted[j])
                        pairs.append((a, b))
                if pairs:
                    conds = [and_(DrugInteraction.medication_a_id == a, DrugInteraction.medication_b_id == b) for a, b in pairs]
                    rows = DrugInteraction.query.filter(DrugInteraction.is_active == True).filter(or_(*conds)).all()
                    for row in rows:
                        a = db.session.get(Medication, row.medication_a_id)
                        b = db.session.get(Medication, row.medication_b_id)
                        warnings.append(f'تحذير: تداخل دوائي {a.trade_name if a else row.medication_a_id} ↔ {b.trade_name if b else row.medication_b_id} ({row.severity})')
            except Exception:
                pass

            prescription.total_cost = total_cost
            visit.prescription_issued = True

            if non_catalog_medications:
                try:
                    from models.notification import Notification
                    dept = Department.query.filter(
                        db.or_(
                            Department.name.ilike('%pharmacy%'),
                            Department.name_ar.ilike('%صيدل%')
                        )
                    ).first()
                    dept_id = dept.id if dept else None
                    notif = Notification(
                        title='طلب إضافة أدوية غير موجودة',
                        message=f'تمت كتابة وصفة تحتوي على أدوية غير موجودة في النظام:\n{non_catalog_medications}\nالزيارة رقم: {visit.id}\nالطبيب: {current_user.full_name}',
                        notification_type='info',
                        priority='normal',
                        recipient_role='pharmacist',
                        recipient_department_id=dept_id,
                        sender_id=current_user.id
                    )
                    db.session.add(notif)
                except Exception:
                    pass

            save_template = (request.form.get('save_as_template') or '') == 'on'
            template_name = (request.form.get('template_name') or '').strip()
            if save_template and template_name:
                try:
                    import secrets
                    tpl_items = []
                    for it in prescription.items.all():
                        label = ''
                        try:
                            m = it.medication
                            if m:
                                label = f"{m.trade_name}{f' ({m.generic_name})' if m.generic_name else ''} — {m.scientific_name} — {m.strength} {m.dosage_form}"
                        except Exception:
                            label = ''
                        dosage_part = it.dosage or ''
                        freq_part = ''
                        if ' | ' in dosage_part:
                            dosage_part, freq_part = dosage_part.split(' | ', 1)
                        tpl_items.append({
                            'medication_id': it.medication_id,
                            'medication_label': label,
                            'dosage': (dosage_part or '').strip(),
                            'frequency': (freq_part or '').strip(),
                            'duration_days': it.duration_days,
                            'quantity': it.quantity,
                            'instructions': it.instructions or ''
                        })
                    new_tpl = {
                        'id': secrets.token_hex(8),
                        'name': template_name,
                        'items': tpl_items
                    }
                    cfg = SystemConfig.query.filter_by(config_key=templates_key).first()
                    if not cfg:
                        cfg = SystemConfig(
                            config_key=templates_key,
                            config_type='json',
                            config_value='[]',
                            category='general',
                            description='قوالب وصفات الطبيب',
                            is_system=False,
                            is_encrypted=False,
                            created_by=current_user.id,
                            updated_by=current_user.id
                        )
                        db.session.add(cfg)
                    existing = cfg.get_value() if cfg and cfg.config_type == 'json' else []
                    if not isinstance(existing, list):
                        existing = []
                    existing.append(new_tpl)
                    cfg.set_value(existing)
                    cfg.updated_by = current_user.id
                except Exception:
                    pass

            db.session.commit()

            for w in warnings:
                flash(w, 'warning')
            try:
                db.session.add(AuditTrail(
                    entity_type='visit',
                    entity_id=visit_id,
                    action='update',
                    user_id=current_user.id,
                    user_ip=request.remote_addr,
                    user_agent=request.headers.get('User-Agent'),
                    description='إضافة وصفة طبية',
                    new_values=json.dumps({'prescription_id': prescription.id, 'items_count': prescription.items.count()})
                ))
                db.session.commit()
            except Exception:
                pass

            flash('تم حفظ الوصفة بنجاح', 'success')
            return redirect(url_for('doctor.patient_details', visit_id=visit_id))

        return render_template(
            'doctor/prescription.html',
            visit=visit,
            medications=medications,
            doctor_templates=doctor_templates,
            visit_prescriptions=visit_prescriptions
        )
    except Exception as e:
        logging.error(f"Error in prescription: {str(e)}")
        flash('حدث خطأ في حفظ الوصفة', 'error')
        return redirect(url_for('doctor.patient_queue'))

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
                pass
            flash('تم تدوين مذكرة التحاليل. يتوجه المريض للاستقبال لإنشاء زيارة للمختبر عند رغبة التنفيذ داخل المركز.', 'info')
            return redirect(url_for('doctor.patient_details', visit_id=visit_id))
        return redirect(url_for('doctor.patient_details', visit_id=visit_id))
    except Exception as e:
        logging.error(f"Error in lab_request: {str(e)}")
        flash('حدث خطأ أثناء إنشاء طلب المختبر', 'error')
        return redirect(url_for('doctor.patient_details', visit_id=visit_id))

@doctor_bp.route('/radiology-request/<int:visit_id>', methods=['GET', 'POST'])
@login_required
@role_required('doctor', 'admin', 'manager')
def radiology_request(visit_id):
    try:
        visit = db.session.get(Visit, visit_id)
        if not visit or visit.doctor_id != current_user.id:
            flash('الزيارة غير موجودة أو ليس لديك صلاحية', 'error')
            return redirect(url_for('doctor.patient_queue'))
        if visit.status != 'IN_PROGRESS':
            flash('لا يمكن طلب تصوير أشعة إلا أثناء سير العلاج', 'warning')
            return redirect(url_for('doctor.patient_details', visit_id=visit_id))
        if request.method == 'POST':
            test_name = request.form.get('test_name') or ''
            notes = request.form.get('notes') or request.form.get('test_description') or ''
            memo_parts = []
            if test_name:
                memo_parts.append(f"نوع التصوير: {test_name}")
            if notes:
                memo_parts.append(f"الوصف: {notes}")
            memo_text = "[مذكرة تصوير]\n" + ("\n".join(memo_parts) if memo_parts else "يرجى إجراء التصوير لدى مركز مناسب.")
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
                    description='إضافة مذكرة تصوير'
                ))
                db.session.commit()
            except Exception:
                pass
            flash('تم تدوين مذكرة التصوير. يتوجه المريض للاستقبال لإنشاء زيارة لقسم الأشعة عند رغبة التنفيذ داخل المركز.', 'info')
            return redirect(url_for('doctor.patient_details', visit_id=visit_id))
        return redirect(url_for('doctor.patient_details', visit_id=visit_id))
    except Exception as e:
        logging.error(f"Error in radiology_request: {str(e)}")
        flash('حدث خطأ أثناء إنشاء طلب الأشعة', 'error')
        return redirect(url_for('doctor.patient_details', visit_id=visit_id))

@doctor_bp.route('/visit-summary/<int:visit_id>')
@login_required
@role_required('doctor', 'admin', 'manager')
def visit_summary(visit_id):
    """ملخص الزيارة"""
    
    try:
        visit = db.session.get(Visit, visit_id)
        if not visit or visit.doctor_id != current_user.id:
            flash('الزيارة غير موجودة أو ليس لديك صلاحية', 'error')
            return redirect(url_for('doctor.patient_queue'))
        
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
        visit = db.session.get(Visit, visit_id)
        if not visit or visit.doctor_id != current_user.id:
            return jsonify({'success': False, 'message': 'الزيارة غير موجودة أو ليست لك'}), 404
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
            except Exception:
                pass

        try:
            _sync_follow_up_request_for_visit(visit, current_user.id)
        except Exception:
            pass

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
        except Exception:
            pass
        return jsonify({'success': True})
    except Exception as e:
        logging.error(f"Error saving visit summary: {str(e)}")
        return jsonify({'success': False, 'message': 'فشل حفظ ملخص الزيارة'}), 500

@doctor_bp.route('/notes/<int:visit_id>', methods=['GET', 'POST'])
@login_required
@role_required('doctor', 'admin', 'manager')
def notes(visit_id):
    """كتابة الملاحظات الطبية"""
    
    try:
        visit = db.session.get(Visit, visit_id)
        if not visit or visit.doctor_id != current_user.id:
            flash('الزيارة غير موجودة أو ليس لديك صلاحية', 'error')
            return redirect(url_for('doctor.patient_queue'))
        if visit.status == 'ARCHIVED':
            flash('لا يمكن إضافة ملاحظات بعد أرشفة الزيارة', 'warning')
            return redirect(url_for('doctor.patient_queue'))
        
        note_type = request.args.get('type') or request.form.get('note_type')
        prefill_notes = None
        if note_type == 'lab':
            prefill_notes = "مذكرة تحاليل:\nنوع الفحص:\nسبب الفحص:\nتعليمات إضافية:"
        elif note_type == 'radiology':
            prefill_notes = "مذكرة تصوير:\nنوع التصوير:\nمنطقة التصوير:\nتعليمات إضافية:"
        elif note_type == 'general':
            prefill_notes = "مذكرة عامة:\nالموضوع:\nتفاصيل:\nتعليمات للمريض:"
        
        if request.method == 'POST':
            medical_notes = request.form.get('medical_notes')
            if medical_notes:
                # إضافة الملاحظات الطبية
                if not visit.notes:
                    visit.notes = ""
                label = '[ملاحظات طبية]'
                if note_type == 'lab':
                    label = '[مذكرة تحاليل]'
                elif note_type == 'radiology':
                    label = '[مذكرة تصوير]'
                elif note_type == 'general':
                    label = '[مذكرة عامة]'
                from datetime import timezone
                visit.notes += f"\n{label} - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} - الطبيب: {current_user.full_name}\n{medical_notes}"
                db.session.commit()
                try:
                    db.session.add(AuditTrail(
                        entity_type='visit',
                        entity_id=visit_id,
                        action='update',
                        user_id=current_user.id,
                        user_ip=request.remote_addr,
                        user_agent=request.headers.get('User-Agent'),
                        description='إضافة ملاحظات طبية'
                    ))
                    db.session.commit()
                except Exception:
                    pass
                flash('تم حفظ الملاحظات الطبية بنجاح', 'success')
                return redirect(url_for('doctor.patient_queue'))
        
        return render_template('doctor/notes.html', visit=visit, note_type=note_type, prefill_notes=prefill_notes)
    except Exception as e:
        logging.exception("Error in notes")
        if current_app.config.get('TESTING'):
            raise
        flash('حدث خطأ في حفظ الملاحظات', 'error')
        return redirect(url_for('doctor.patient_queue'))


@doctor_bp.route('/api/note-templates', methods=['GET'])
@login_required
@role_required('doctor', 'admin', 'manager', 'super_admin')
def api_note_templates():
    templates = _get_doctor_note_templates()
    active_only = (request.args.get('active_only') or 'true').strip().lower() in {'1', 'true', 'yes', 'on'}
    out = []
    for t in templates:
        if not isinstance(t, dict):
            continue
        if active_only and not t.get('is_active', True):
            continue
        out.append(t)
    return jsonify({'success': True, 'templates': out}), 200

@doctor_bp.route('/api/dashboard-layout', methods=['GET', 'POST'])
@login_required
@role_required('doctor', 'admin', 'manager', 'super_admin')
def api_dashboard_layout():
    if request.method == 'GET':
        return jsonify({'success': True, 'items': _get_doctor_dashboard_layout()}), 200
    data = request.get_json() or {}
    items = data.get('items') or []
    allowed = {i['id'] for i in _default_doctor_dashboard_layout()}
    normalized = []
    for item in items:
        if not isinstance(item, dict):
            continue
        panel_id = item.get('id')
        if panel_id not in allowed:
            continue
        normalized.append({
            'id': panel_id,
            'title': item.get('title') or '',
            'order': int(item.get('order') or 0),
            'enabled': bool(item.get('enabled', True))
        })
    if not normalized:
        normalized = _default_doctor_dashboard_layout()
    _save_doctor_dashboard_layout(normalized)
    return jsonify({'success': True, 'items': normalized}), 200


@doctor_bp.route('/api/note-templates', methods=['POST'])
@login_required
@role_required('doctor', 'admin', 'manager', 'super_admin')
def upsert_note_template():
    payload = request.get_json(silent=True) if request.is_json else request.form
    template_id = (payload.get('id') or '').strip() or None
    name = (payload.get('name') or '').strip()
    text = payload.get('text') or ''
    is_active = payload.get('is_active')
    if isinstance(is_active, str):
        is_active = is_active.strip().lower() in {'1', 'true', 'yes', 'on'}
    if is_active is None:
        is_active = True
    if not name:
        return jsonify({'success': False, 'message': 'اسم القالب مطلوب'}), 400

    templates = _get_doctor_note_templates()
    if template_id:
        updated = False
        for t in templates:
            if isinstance(t, dict) and t.get('id') == template_id:
                t['name'] = name
                t['text'] = text
                t['is_active'] = bool(is_active)
                updated = True
                break
        if not updated:
            return jsonify({'success': False, 'message': 'القالب غير موجود'}), 404
        _save_doctor_note_templates(templates)
        return jsonify({'success': True, 'id': template_id}), 200

    new_id = secrets.token_hex(8)
    templates.append({'id': new_id, 'name': name, 'text': text, 'is_active': bool(is_active)})
    _save_doctor_note_templates(templates)
    return jsonify({'success': True, 'id': new_id}), 201


@doctor_bp.route('/api/note-templates/<string:template_id>/delete', methods=['POST'])
@login_required
@role_required('doctor', 'admin', 'manager', 'super_admin')
def delete_note_template(template_id: str):
    templates = _get_doctor_note_templates()
    before = len(templates)
    templates = [t for t in templates if not (isinstance(t, dict) and t.get('id') == template_id)]
    if len(templates) == before:
        return jsonify({'success': False, 'message': 'القالب غير موجود'}), 404
    _save_doctor_note_templates(templates)
    return jsonify({'success': True}), 200

@doctor_bp.route('/end-treatment/<int:visit_id>', methods=['POST'])
@login_required
@role_required('doctor', 'admin', 'manager')
def end_treatment(visit_id):
    """إنهاء العلاج"""
    
    try:
        visit = db.session.get(Visit, visit_id)
        if not visit or visit.doctor_id != current_user.id:
            flash('الزيارة غير موجودة أو ليس لديك صلاحية', 'error')
            return redirect(url_for('doctor.patient_queue'))
        if visit.status != 'IN_PROGRESS':
            flash('لا يمكن إنهاء العلاج إلا أثناء سير العلاج', 'warning')
            return redirect(url_for('doctor.patient_queue'))
        from models.queue_management import QueueManagement
        from services.queue_management_service import QueueManagementService
        ticket = QueueManagement.query.filter_by(
            visit_id=visit_id,
            department_id=visit.department_id
        ).filter(QueueManagement.status == 'in_progress').order_by(desc(QueueManagement.started_at)).first()
        if ticket:
            ok, msg = QueueManagementService().complete_treatment(ticket.id, completed_by=current_user.id)
            if not ok:
                flash(msg, 'warning')
                return redirect(url_for('doctor.patient_queue'))
        visit.status = 'COMPLETED'
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
        except Exception:
            pass
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
        except Exception:
            pass
        
        flash('تم تسجيل إنهاء العلاج وإخطار الاستقبال', 'success')
        return redirect(url_for('doctor.patient_queue'))
    except Exception as e:
        logging.error(f"Error ending treatment: {str(e)}")
        flash('حدث خطأ في إنهاء العلاج', 'error')
        return redirect(url_for('doctor.patient_queue'))

# مسارات إضافية للطبيب الاحترافي

@doctor_bp.route('/medical-history/<int:patient_id>')
@login_required
@role_required('doctor', 'admin', 'manager')
def medical_history(patient_id):
    """السجل الطبي للمريض"""
    
    try:
        patient = db.session.get(Patient, patient_id)
        if not patient:
            flash('المريض غير موجود', 'error')
            return redirect(url_for('doctor.patient_queue'))
        
        # جلب السجل الطبي الكامل
        medical_records = MedicalRecord.query.filter(
            MedicalRecord.patient_id == patient_id
        ).order_by(desc(MedicalRecord.created_at)).all()
        
        previous_visits = Visit.query.filter(
            Visit.patient_id == patient_id
        ).order_by(desc(Visit.visit_date)).limit(10).all()
        
        return render_template('doctor/medical_history.html',
                             patient=patient,
                             medical_records=medical_records,
                             previous_visits=previous_visits)
    except Exception as e:
        logging.error(f"Error loading medical history: {str(e)}")
        flash('حدث خطأ في تحميل السجل الطبي', 'error')
        return redirect(url_for('doctor.patient_queue'))

@doctor_bp.route('/prescriptions-history/<int:patient_id>')
@login_required
@role_required('doctor', 'admin', 'manager')
def prescriptions_history(patient_id):
    """تاريخ الوصفات الطبية للمريض"""
    
    try:
        patient = db.session.get(Patient, patient_id)
        if not patient:
            flash('المريض غير موجود', 'error')
            return redirect(url_for('doctor.patient_queue'))
        
        # جلب الوصفات السابقة
        prescriptions = Prescription.query.filter(
            Prescription.patient_id == patient_id
        ).order_by(desc(Prescription.created_at)).all()
        
        return render_template('doctor/prescriptions_history.html',
                             patient=patient,
                             prescriptions=prescriptions)
    except Exception as e:
        logging.error(f"Error loading prescriptions history: {str(e)}")
        flash('حدث خطأ في تحميل تاريخ الوصفات', 'error')
        return redirect(url_for('doctor.patient_queue'))

@doctor_bp.route('/lab-results/<int:patient_id>')
@login_required
def lab_results(patient_id):
    flash('عرض نتائج المختبر غير متاح للطبيب ضمن تقسيم المهام الجديد. يرجى تدوين الملاحظة إن لزم، ثم يقوم الاستقبال بإنشاء زيارة جديدة لقسم المختبر مع التكاليف المناسبة.', 'warning')
    return redirect(url_for('doctor.patient_queue'))

@doctor_bp.route('/radiology-results/<int:patient_id>')
@login_required
def radiology_results(patient_id):
    flash('عرض نتائج الأشعة غير متاح للطبيب ضمن تقسيم المهام الجديد. يرجى تدوين الملاحظة إن لزم، ثم يقوم الاستقبال بإنشاء زيارة جديدة لقسم الأشعة مع التكاليف المناسبة.', 'warning')
    return redirect(url_for('doctor.patient_queue'))

@doctor_bp.route('/print-prescription/<int:prescription_id>')
@login_required
@role_required('doctor', 'admin', 'manager')
def print_prescription(prescription_id):
    """طباعة الوصفة الطبية"""
    
    try:
        prescription = db.session.get(Prescription, prescription_id)
        if not prescription:
            flash('الوصفة غير موجودة', 'error')
            return redirect(url_for('doctor.patient_queue'))
        
        return render_template('print/prescription.html',
                             prescription=prescription)
    except Exception as e:
        logging.error(f"Error printing prescription: {str(e)}")
        flash('حدث خطأ في طباعة الوصفة', 'error')
        return redirect(url_for('doctor.patient_queue'))

@doctor_bp.route('/print-medical-report/<int:visit_id>')
@login_required
@role_required('doctor', 'admin', 'manager')
def print_medical_report(visit_id):
    """طباعة التقرير الطبي"""
    
    try:
        visit = db.session.get(Visit, visit_id)
        if not visit or visit.doctor_id != current_user.id:
            flash('الزيارة غير موجودة أو ليس لديك صلاحية', 'error')
            return redirect(url_for('doctor.patient_queue'))
        
        return render_template('doctor/print_medical_report.html',
                             visit=visit)
    except Exception as e:
        logging.error(f"Error printing medical report: {str(e)}")
        flash('حدث خطأ في طباعة التقرير الطبي', 'error')
        return redirect(url_for('doctor.patient_queue'))

# ==================== الميزات الذكية للطبيب ====================

def get_ai_diagnostic_assistant():
    """مساعد التشخيص بالذكاء الاصطناعي"""
    try:
        from models.visit import Visit
        from models.medical_record import MedicalRecord
        from models.medication import Prescription
        from datetime import datetime, timedelta
        
        # تحليل التشخيصات الشائعة
        common_diagnoses = db.session.query(
            MedicalRecord.diagnosis,
            func.count(MedicalRecord.id).label('count')
        ).join(Visit, MedicalRecord.visit_id == Visit.id).filter(
            Visit.doctor_id == current_user.id,
            MedicalRecord.created_at >= datetime.now() - timedelta(days=30)
        ).group_by(MedicalRecord.diagnosis).order_by(func.count(MedicalRecord.id).desc()).limit(5).all()
        
        # تحليل الأدوية الموصوفة
        common_medications = db.session.query(
            Prescription.medication_name,
            func.count(Prescription.id).label('count')
        ).join(Visit, Prescription.visit_id == Visit.id).filter(
            Visit.doctor_id == current_user.id,
            Prescription.created_at >= datetime.now() - timedelta(days=30)
        ).group_by(Prescription.medication_name).order_by(func.count(Prescription.id).desc()).limit(5).all()
        
        # اقتراحات التشخيص
        diagnostic_suggestions = []
        
        # تحليل الأعراض الشائعة
        if common_diagnoses:
            top_diagnosis = common_diagnoses[0]
            diagnostic_suggestions.append({
                'type': 'common_diagnosis',
                'title': 'التشخيص الأكثر شيوعاً',
                'diagnosis': top_diagnosis.diagnosis,
                'frequency': top_diagnosis.count,
                'suggestion': f'هذا التشخيص شائع في ممارستك ({top_diagnosis.count} مرة)'
            })
        
        # تحليل الأدوية
        if common_medications:
            top_medication = common_medications[0]
            diagnostic_suggestions.append({
                'type': 'common_medication',
                'title': 'الدواء الأكثر وصفاً',
                'medication': top_medication.medication_name,
                'frequency': top_medication.count,
                'suggestion': f'هذا الدواء شائع في وصفاتك ({top_medication.count} مرة)'
            })
        
        return {
            'common_diagnoses': [{'diagnosis': d.diagnosis, 'count': d.count} for d in common_diagnoses],
            'common_medications': [{'medication': m.medication_name, 'count': m.count} for m in common_medications],
            'diagnostic_suggestions': diagnostic_suggestions
        }
    except Exception as e:
        logging.debug(f"Error getting AI diagnostic assistant: {str(e)}")
        return {}

def get_standardized_pathways(diagnosis_text: str):
    diagnosis_text = (diagnosis_text or '').strip().lower()
    if not diagnosis_text:
        return []
    pathways = [
        {
            'id': 'diabetes_basic',
            'keywords': ['سكري', 'diabetes'],
            'title': 'مسار السكري الأساسي',
            'steps': ['قياس HbA1c', 'تثقيف غذائي', 'خطة متابعة خلال 4 أسابيع']
        },
        {
            'id': 'hypertension_basic',
            'keywords': ['ضغط', 'hypertension'],
            'title': 'مسار ارتفاع الضغط',
            'steps': ['قياس ضغط متكرر', 'تقييم عوامل الخطر', 'تعديل نمط الحياة']
        },
        {
            'id': 'asthma_basic',
            'keywords': ['ربو', 'asthma'],
            'title': 'مسار الربو',
            'steps': ['تقييم شدة الأعراض', 'خطة بخاخات', 'تثقيف عن المحفزات']
        },
        {
            'id': 'uti_basic',
            'keywords': ['التهاب بول', 'uti'],
            'title': 'مسار التهاب المسالك البولية',
            'steps': ['تحليل بول', 'تقييم عوامل الخطورة', 'خطة علاج قصيرة']
        }
    ]
    matched = []
    for p in pathways:
        if any(k in diagnosis_text for k in p['keywords']):
            matched.append({'id': p['id'], 'title': p['title'], 'steps': p['steps']})
    return matched

def get_data_based_recommendations(diagnosis_text: str):
    diagnosis_text = (diagnosis_text or '').strip()
    if not diagnosis_text:
        return []
    try:
        from models.medication import PrescriptionItem, Medication, Prescription
        from datetime import datetime, timedelta
        since = datetime.now() - timedelta(days=120)
        rows = db.session.query(
            Medication.trade_name,
            func.count(PrescriptionItem.id).label('cnt')
        ).join(PrescriptionItem.prescription).join(PrescriptionItem.medication).filter(
            Prescription.diagnosis.ilike(f'%{diagnosis_text}%'),
            Prescription.created_at >= since
        ).group_by(Medication.trade_name).order_by(func.count(PrescriptionItem.id).desc()).limit(5).all()
        out = []
        for r in rows:
            out.append({'medication': r.trade_name, 'count': int(r.cnt)})
        return out
    except Exception:
        return []

def evaluate_clinical_rules(visit, prescriptions, structured_vital_signs=None):
    warnings = []
    try:
        from models.patient import PatientAllergy
        allergies = PatientAllergy.query.filter_by(patient_id=visit.patient_id).all()
        allergens = [a.allergen.lower() for a in allergies if a.allergen]
    except Exception:
        allergens = []
    med_names = []
    durations = []
    for rx in prescriptions or []:
        for item in rx.items:
            if item.medication and item.medication.trade_name:
                med_names.append(item.medication.trade_name.lower())
            if item.duration_days:
                durations.append(item.duration_days)
    dupes = set([m for m in med_names if med_names.count(m) > 1])
    if dupes:
        warnings.append({
            'type': 'duplicate_medication',
            'title': 'تكرار دواء',
            'message': 'هناك تكرار لأدوية في الوصفة الحالية'
        })
    if allergens:
        for med in med_names:
            if any(a in med for a in allergens):
                warnings.append({
                    'type': 'allergy',
                    'title': 'تحذير حساسية',
                    'message': 'قد يتعارض دواء مع حساسية مسجلة للمريض'
                })
                break
    if any((d or 0) > 30 for d in durations):
        warnings.append({
            'type': 'long_duration',
            'title': 'مدة علاج طويلة',
            'message': 'هناك أدوية بمدة تتجاوز 30 يوماً'
        })
    diag = (visit.diagnosis or '').lower()
    vitals = structured_vital_signs or {}
    if ('ضغط' in diag or 'hypertension' in diag) and not vitals.get('blood_pressure'):
        warnings.append({
            'type': 'missing_vitals',
            'title': 'ضغط الدم غير مسجل',
            'message': 'التشخيص يتطلب تسجيل ضغط الدم'
        })
    if ('سكري' in diag or 'diabetes' in diag) and not vitals.get('blood_pressure'):
        warnings.append({
            'type': 'missing_vitals',
            'title': 'علامات حيوية ناقصة',
            'message': 'يفضل تسجيل العلامات الحيوية لتقييم الحالة'
        })
    return warnings

def get_patient_medical_history_ai():
    """ذكاء اصطناعي لتاريخ المريض الطبي"""
    try:
        from models.visit import Visit
        from models.medical_record import MedicalRecord
        from models.medication import Prescription
        from models.patient import Patient
        from datetime import datetime, timedelta
        
        # تحليل المرضى المتكررين
        frequent_patients = db.session.query(
            Visit.patient_id,
            func.count(Visit.id).label('visit_count'),
            func.max(Visit.visit_date).label('last_visit')
        ).filter(
            Visit.doctor_id == current_user.id,
            Visit.visit_date >= datetime.now().date() - timedelta(days=90)
        ).group_by(Visit.patient_id).having(func.count(Visit.id) > 2).all()
        
        # تحليل الحالات المزمنة
        chronic_conditions = db.session.query(
            MedicalRecord.diagnosis,
            func.count(MedicalRecord.id).label('frequency')
        ).join(Visit, MedicalRecord.visit_id == Visit.id).filter(
            Visit.doctor_id == current_user.id,
            MedicalRecord.diagnosis.in_(['السكري', 'الضغط', 'القلب', 'الربو', 'السرطان'])
        ).group_by(MedicalRecord.diagnosis).all()
        
        # تحليل الأدوية طويلة المدى
        long_term_medications = db.session.query(
            Prescription.medication_name,
            func.count(Prescription.id).label('frequency')
        ).join(Visit, Prescription.visit_id == Visit.id).filter(
            Visit.doctor_id == current_user.id,
            Prescription.created_at >= datetime.now() - timedelta(days=90)
        ).group_by(Prescription.medication_name).having(func.count(Prescription.id) > 3).all()
        
        return {
            'frequent_patients': [
                {
                    'patient_id': p.patient_id,
                    'visit_count': p.visit_count,
                    'last_visit': p.last_visit.strftime('%Y-%m-%d') if p.last_visit else None
                } for p in frequent_patients
            ],
            'chronic_conditions': [{'condition': c.diagnosis, 'frequency': c.frequency} for c in chronic_conditions],
            'long_term_medications': [{'medication': m.medication_name, 'frequency': m.frequency} for m in long_term_medications]
        }
    except Exception as e:
        logging.debug(f"Error getting patient medical history AI: {str(e)}")
        return {}

def get_treatment_recommendations():
    """توصيات العلاج الذكية"""
    try:
        from models.visit import Visit
        from models.medical_record import MedicalRecord
        from models.medication import Prescription
        from datetime import datetime, timedelta
        
        recommendations = []
        
        # تحليل نجاح العلاجات
        successful_treatments = db.session.query(
            MedicalRecord.diagnosis,
            Prescription.medication_name,
            func.count(MedicalRecord.id).label('success_count')
        ).join(Visit, MedicalRecord.visit_id == Visit.id).join(
            Prescription, Visit.id == Prescription.visit_id
        ).filter(
            Visit.doctor_id == current_user.id,
            Visit.status == 'ARCHIVED',
            MedicalRecord.created_at >= datetime.now() - timedelta(days=60)
        ).group_by(MedicalRecord.diagnosis, Prescription.medication_name).all()
        
        # تحليل العلاجات الفعالة
        if successful_treatments:
            top_treatment = max(successful_treatments, key=lambda x: x.success_count)
            recommendations.append({
                'type': 'effective_treatment',
                'title': 'علاج فعال',
                'diagnosis': top_treatment.diagnosis,
                'medication': top_treatment.medication_name,
                'success_rate': top_treatment.success_count,
                'suggestion': f'هذا العلاج فعال للتشخيص: {top_treatment.diagnosis}'
            })
        
        # تحليل الأدوية المتفاعلة
        drug_interactions = check_drug_interactions()
        if drug_interactions:
            recommendations.append({
                'type': 'drug_interaction',
                'title': 'تفاعل دوائي',
                'interactions': drug_interactions,
                'suggestion': 'تحقق من التفاعلات الدوائية قبل الوصف'
            })
        
        return recommendations
    except Exception as e:
        logging.error(f"Error getting treatment recommendations: {str(e)}")
        return []

def get_drug_interaction_checker():
    """فحص التفاعلات الدوائية"""
    try:
        from models.medication import Prescription
        from models.visit import Visit
        from datetime import datetime, timedelta
        
        # قائمة التفاعلات المعروفة (مبسطة)
        known_interactions = {
            'وارفارين': ['أسبرين', 'إيبوبروفين'],
            'ديجوكسين': ['فوروسيميد', 'سبيرونولاكتون'],
            'ميثوتريكسات': ['فوليك أسيد', 'تريميثوبريم']
        }
        
        # فحص الوصفات الحديثة
        recent_prescriptions = Prescription.query.join(Visit).filter(
            Visit.doctor_id == current_user.id,
            Prescription.created_at >= datetime.now() - timedelta(days=7)
        ).all()
        
        interactions_found = []
        
        for prescription in recent_prescriptions:
            medication = prescription.medication_name
            if medication in known_interactions:
                for other_med in known_interactions[medication]:
                    # فحص إذا كان المريض يتناول الدواء الآخر
                    other_prescription = Prescription.query.join(Visit).filter(
                        Visit.patient_id == prescription.visit.patient_id,
                        Prescription.medication_name == other_med,
                        Prescription.created_at >= datetime.now() - timedelta(days=30)
                    ).first()
                    
                    if other_prescription:
                        interactions_found.append({
                            'medication1': medication,
                            'medication2': other_med,
                            'severity': 'متوسط',
                            'description': f'تفاعل محتمل بين {medication} و {other_med}'
                        })
        
        return {
            'interactions_found': interactions_found,
            'total_prescriptions_checked': len(recent_prescriptions),
            'interaction_rate': len(interactions_found) / len(recent_prescriptions) * 100 if recent_prescriptions else 0
        }
    except Exception as e:
        logging.error(f"Error getting drug interaction checker: {str(e)}")
        return {}

def get_clinical_decision_support():
    """دعم القرارات السريرية"""
    try:
        from models.visit import Visit
        from models.medical_record import MedicalRecord
        from models.medication import Prescription
        from datetime import datetime, timedelta
        
        support_recommendations = []
        
        # تحليل معدل نجاح التشخيصات
        diagnosis_success = db.session.query(
            MedicalRecord.diagnosis,
            func.count(MedicalRecord.id).label('total_cases'),
            func.sum(case([(Visit.status == 'ARCHIVED', 1)], else_=0)).label('successful_cases')
        ).join(Visit, MedicalRecord.visit_id == Visit.id).filter(
            Visit.doctor_id == current_user.id,
            MedicalRecord.created_at >= datetime.now() - timedelta(days=30)
        ).group_by(MedicalRecord.diagnosis).all()
        
        for diagnosis in diagnosis_success:
            success_rate = (diagnosis.successful_cases / diagnosis.total_cases * 100) if diagnosis.total_cases > 0 else 0
            if success_rate < 70:
                support_recommendations.append({
                    'type': 'diagnosis_improvement',
                    'title': 'تحسين التشخيص',
                    'diagnosis': diagnosis.diagnosis,
                    'success_rate': round(success_rate, 2),
                    'suggestion': f'معدل نجاح التشخيص {diagnosis.diagnosis} منخفض - يحتاج مراجعة'
                })
        
        # تحليل فعالية الأدوية
        medication_effectiveness = db.session.query(
            Prescription.medication_name,
            func.count(Prescription.id).label('total_prescriptions'),
            func.sum(case([(Visit.status == 'ARCHIVED', 1)], else_=0)).label('successful_treatments')
        ).join(Visit, Prescription.visit_id == Visit.id).filter(
            Visit.doctor_id == current_user.id,
            Prescription.created_at >= datetime.now() - timedelta(days=30)
        ).group_by(Prescription.medication_name).all()
        
        for medication in medication_effectiveness:
            effectiveness_rate = (medication.successful_treatments / medication.total_prescriptions * 100) if medication.total_prescriptions > 0 else 0
            if effectiveness_rate < 60:
                support_recommendations.append({
                    'type': 'medication_effectiveness',
                    'title': 'فعالية الدواء',
                    'medication': medication.medication_name,
                    'effectiveness_rate': round(effectiveness_rate, 2),
                    'suggestion': f'فعالية الدواء {medication.medication_name} منخفضة - يحتاج مراجعة'
                })
        
        return support_recommendations
    except Exception as e:
        logging.error(f"Error getting clinical decision support: {str(e)}")
        return []

def get_medical_analytics():
    """التحليلات الطبية"""
    try:
        from models.visit import Visit
        from models.medical_record import MedicalRecord
        from models.medication import Prescription
        from datetime import datetime, timedelta
        
        # تحليل الأداء الطبي
        total_visits = Visit.query.filter(Visit.doctor_id == current_user.id).count()
        completed_visits = Visit.query.filter(
            Visit.doctor_id == current_user.id,
            Visit.status == 'ARCHIVED'
        ).count()
        
        completion_rate = (completed_visits / total_visits * 100) if total_visits > 0 else 0
        
        # تحليل متوسط مدة الزيارة
        avg_visit_duration = db.session.query(func.avg(Visit.duration)).filter(
            Visit.doctor_id == current_user.id
        ).scalar() or 0
        
        # تحليل التشخيصات
        diagnosis_distribution = db.session.query(
            MedicalRecord.diagnosis,
            func.count(MedicalRecord.id).label('count')
        ).join(Visit, MedicalRecord.visit_id == Visit.id).filter(
            Visit.doctor_id == current_user.id,
            MedicalRecord.created_at >= datetime.now() - timedelta(days=30)
        ).group_by(MedicalRecord.diagnosis).all()
        
        # تحليل الأدوية
        medication_distribution = db.session.query(
            Prescription.medication_name,
            func.count(Prescription.id).label('count')
        ).join(Visit, Prescription.visit_id == Visit.id).filter(
            Visit.doctor_id == current_user.id,
            Prescription.created_at >= datetime.now() - timedelta(days=30)
        ).group_by(Prescription.medication_name).all()
        
        return {
            'completion_rate': round(completion_rate, 2),
            'avg_visit_duration': round(avg_visit_duration, 2),
            'diagnosis_distribution': [{'diagnosis': d.diagnosis, 'count': d.count} for d in diagnosis_distribution],
            'medication_distribution': [{'medication': m.medication_name, 'count': m.count} for m in medication_distribution],
            'performance_score': calculate_medical_performance_score(completion_rate, avg_visit_duration)
        }
    except Exception as e:
        logging.error(f"Error getting medical analytics: {str(e)}")
        return {}

def get_workflow_optimization():
    """تحسين سير العمل"""
    try:
        from models.visit import Visit
        from models.appointment import Appointment
        from datetime import datetime, timedelta
        
        optimizations = []
        
        # تحليل أوقات الذروة
        peak_hours = db.session.query(
            func.extract('hour', Visit.visit_time).label('hour'),
            func.count(Visit.id).label('count')
        ).filter(
            Visit.doctor_id == current_user.id,
            Visit.visit_date >= datetime.now().date() - timedelta(days=30)
        ).group_by(func.extract('hour', Visit.visit_time)).all()
        
        if peak_hours:
            max_hour = max(peak_hours, key=lambda x: x.count)
            if max_hour.count > 10:
                optimizations.append({
                    'type': 'peak_hours',
                    'title': 'ساعات الذروة',
                    'description': f'الساعة {max_hour.hour}:00 هي الأكثر ازدحاماً ({max_hour.count} زيارة)',
                    'suggestion': 'توزيع المواعيد على ساعات أخرى'
                })
        
        # تحليل المواعيد
        today = datetime.now().date()
        tomorrow_appointments = Appointment.query.filter(
            Appointment.doctor_id == current_user.id,
            db.func.date(Appointment.starts_at) == today + timedelta(days=1)
        ).count()
        
        if tomorrow_appointments > 15:
            optimizations.append({
                'type': 'appointment_load',
                'title': 'عبء المواعيد',
                'description': f'لديك {tomorrow_appointments} موعد غداً',
                'suggestion': 'مراجعة توزيع المواعيد'
            })
        
        # تحليل الكفاءة
        avg_duration = db.session.query(func.avg(Visit.duration)).filter(
            Visit.doctor_id == current_user.id
        ).scalar() or 0
        
        if avg_duration > 45:
            optimizations.append({
                'type': 'efficiency',
                'title': 'تحسين الكفاءة',
                'description': f'متوسط مدة الزيارة: {avg_duration:.1f} دقيقة',
                'suggestion': 'تحسين العمليات لتقليل مدة الزيارة'
            })
        
        return optimizations
    except Exception as e:
        logging.error(f"Error getting workflow optimization: {str(e)}")
        return []

def get_smart_reminders():
    """التذكيرات الذكية"""
    try:
        from models.visit import Visit
        from models.appointment import Appointment
        from models.medication import Prescription
        from datetime import datetime, timedelta
        
        reminders = []
        
        # تذكيرات المواعيد
        today = datetime.now().date()
        tomorrow_appointments = Appointment.query.filter(
            Appointment.doctor_id == current_user.id,
            db.func.date(Appointment.starts_at) == today + timedelta(days=1)
        ).count()
        
        if tomorrow_appointments > 0:
            reminders.append({
                'type': 'appointments',
                'title': 'مواعيد غداً',
                'message': f'لديك {tomorrow_appointments} موعد غداً',
                'priority': 'medium'
            })
        
        # تذكيرات المتابعة
        follow_up_visits = Visit.query.filter(
            Visit.doctor_id == current_user.id,
            Visit.status == 'ARCHIVED',
            Visit.completed_at >= datetime.now() - timedelta(days=7)
        ).count()
        
        if follow_up_visits > 5:
            reminders.append({
                'type': 'follow_up',
                'title': 'متابعة المرضى',
                'message': f'تم إنجاز {follow_up_visits} زيارة هذا الأسبوع - يحتاج متابعة',
                'priority': 'low'
            })
        
        # تذكيرات الأدوية
        recent_prescriptions = Prescription.query.join(Visit).filter(
            Visit.doctor_id == current_user.id,
            Prescription.created_at >= datetime.now() - timedelta(days=3)
        ).count()
        
        if recent_prescriptions > 10:
            reminders.append({
                'type': 'medications',
                'title': 'مراجعة الأدوية',
                'message': f'تم وصف {recent_prescriptions} دواء في آخر 3 أيام',
                'priority': 'low'
            })
        
        return reminders
    except Exception as e:
        logging.error(f"Error getting smart reminders: {str(e)}")
        return []

# دوال مساعدة
def check_drug_interactions():
    """فحص التفاعلات الدوائية"""
    # قائمة مبسطة للتفاعلات المعروفة
    interactions = [
        {'drug1': 'وارفارين', 'drug2': 'أسبرين', 'severity': 'عالي'},
        {'drug1': 'ديجوكسين', 'drug2': 'فوروسيميد', 'severity': 'متوسط'},
        {'drug1': 'ميثوتريكسات', 'drug2': 'تريميثوبريم', 'severity': 'عالي'}
    ]
    return interactions

def calculate_medical_performance_score(completion_rate, avg_duration):
    """حساب نقاط الأداء الطبي"""
    # نقاط الإنجاز
    completion_score = completion_rate
    
    # نقاط الكفاءة (كلما قل الوقت كلما زادت النقاط)
    efficiency_score = max(0, 100 - (avg_duration / 60 * 20))
    
    return (completion_score + efficiency_score) / 2

@doctor_bp.route('/patients')
@login_required
@role_required('doctor', 'admin', 'manager')
def patients():
    """بحث المرضى للطبيب (قراءة فقط)"""

    try:
        q = (request.args.get('q') or '').strip()
        from sqlalchemy import or_, func

        base_query = Patient.query
        if q:
            like = f"%{q}%"
            base_query = base_query.filter(
                or_(
                    Patient.first_name.ilike(like),
                    Patient.last_name.ilike(like),
                    Patient.phone.ilike(like),
                    Patient.national_id.ilike(like),
                    Patient.first_name_ar.ilike(like),
                    Patient.last_name_ar.ilike(like)
                )
            )

        # إحصائيات الزيارات: العدد وآخر زيارة
        visits_count_sub = db.session.query(
            Visit.patient_id.label('pid'),
            func.count(Visit.id).label('visits_count'),
            func.max(Visit.visit_date).label('last_visit')
        ).group_by(Visit.patient_id).subquery()

        patients = base_query.outerjoin(
            visits_count_sub, visits_count_sub.c.pid == Patient.id
        ).add_columns(
            visits_count_sub.c.visits_count, visits_count_sub.c.last_visit
        ).order_by(Patient.id.desc()).limit(100).all()

        # صياغة النتائج لواجهة العرض
        results = []
        for p, visits_count, last_visit in patients:
            results.append({
                'id': p.id,
                'full_name': p.full_name,
                'phone': p.phone,
                'national_id': p.national_id,
                'age': p.age,
                'visits_count': int(visits_count or 0),
                'last_visit': last_visit,
            })

        return render_template('doctor/patients.html', q=q, results=results)
    except Exception as e:
        logging.error(f"Error loading doctor patients search: {str(e)}")
        flash('حدث خطأ في تحميل البحث عن المرضى', 'error')
        return redirect(url_for('doctor.patient_queue'))


@doctor_bp.route('/patient-timeline/<int:patient_id>')
@login_required
@role_required('doctor', 'admin', 'manager')
def patient_timeline(patient_id: int):
    try:
        patient = db.session.get(Patient, patient_id)
        if not patient:
            flash('المريض غير موجود', 'error')
            return redirect(url_for('doctor.patients'))

        filter_type = (request.args.get('type') or '').strip().lower()
        events = []

        visits = Visit.query.filter(Visit.patient_id == patient_id).order_by(Visit.visit_date.desc(), Visit.created_at.desc()).limit(200).all()
        for v in visits:
            dt = None
            if getattr(v, 'visit_date', None) and getattr(v, 'visit_time', None):
                try:
                    dt = datetime.combine(v.visit_date, v.visit_time)
                except Exception:
                    dt = None
            if dt is None:
                dt = v.created_at or datetime.now()
            events.append({
                'type': 'visit',
                'dt': dt,
                'title': f"زيارة ({v.visit_type_display})",
                'status': v.status,
                'details': (v.diagnosis or v.symptoms or v.notes or ''),
                'link': url_for('doctor.patient_details', visit_id=v.id) if v.doctor_id == current_user.id else None
            })

        prescriptions = Prescription.query.filter(Prescription.patient_id == patient_id).order_by(Prescription.created_at.desc()).limit(200).all()
        for rx in prescriptions:
            events.append({
                'type': 'prescription',
                'dt': rx.created_at or datetime.now(),
                'title': 'وصفة طبية',
                'status': getattr(rx, 'status', None),
                'details': (getattr(rx, 'additional_notes', None) or getattr(rx, 'notes', None) or ''),
                'link': url_for('doctor.prescriptions_history', patient_id=patient_id)
            })

        lab_reqs = LabRequest.query.filter(LabRequest.patient_id == patient_id).order_by(LabRequest.created_at.desc()).limit(200).all()
        for lr in lab_reqs:
            events.append({
                'type': 'lab',
                'dt': lr.created_at or datetime.now(),
                'title': f"مختبر: {getattr(lr, 'test_name', None) or getattr(lr, 'test_type', None) or 'طلب'}",
                'status': lr.status,
                'details': (getattr(lr, 'reason', None) or getattr(lr, 'notes', None) or ''),
                'link': None
            })

        rad_reqs = RadiologyRequest.query.filter(RadiologyRequest.patient_id == patient_id).order_by(RadiologyRequest.created_at.desc()).limit(200).all()
        for rr in rad_reqs:
            events.append({
                'type': 'radiology',
                'dt': rr.created_at or datetime.now(),
                'title': f"أشعة: {getattr(rr, 'test_name', None) or getattr(rr, 'modality', None) or 'طلب'}",
                'status': rr.status,
                'details': (getattr(rr, 'clinical_info', None) or getattr(rr, 'notes', None) or ''),
                'link': None
            })

        records = MedicalRecord.query.filter(MedicalRecord.patient_id == patient_id).order_by(MedicalRecord.created_at.desc()).limit(200).all()
        for mr in records:
            events.append({
                'type': 'record',
                'dt': mr.created_at or datetime.now(),
                'title': mr.title or 'سجل طبي',
                'status': None,
                'details': mr.details or '',
                'link': url_for('doctor.medical_history', patient_id=patient_id)
            })

        follow_ups = FollowUpRequest.query.filter(FollowUpRequest.patient_id == patient_id).order_by(FollowUpRequest.created_at.desc()).limit(200).all()
        for fu in follow_ups:
            events.append({
                'type': 'follow_up',
                'dt': datetime.combine(fu.suggested_date, datetime.min.time()) if fu.suggested_date else (fu.created_at or datetime.now()),
                'title': 'متابعة مقترحة',
                'status': fu.status,
                'details': fu.notes or '',
                'link': None
            })

        appointments = Appointment.query.filter(Appointment.patient_id == patient_id).order_by(Appointment.starts_at.desc()).limit(200).all()
        for ap in appointments:
            events.append({
                'type': 'appointment',
                'dt': ap.starts_at or datetime.now(),
                'title': 'موعد',
                'status': ap.status,
                'details': ap.notes or '',
                'link': None
            })

        if filter_type:
            events = [e for e in events if e.get('type') == filter_type]
        events.sort(key=lambda e: e.get('dt') or datetime.now(), reverse=True)

        return render_template('doctor/patient_timeline.html', patient=patient, events=events, filter_type=filter_type)
    except Exception as e:
        logging.error(f"Error in patient timeline: {str(e)}")
        flash('حدث خطأ في تحميل الخط الزمني', 'error')
        return redirect(url_for('doctor.patients'))

@doctor_bp.route('/lab-requests')
@login_required
def lab_requests():
    flash('تم فصل طلبات المختبر عن الطبيب. للاستعلام، يرجى مراجعة قسم المختبر أو الاستقبال.', 'warning')
    return redirect(url_for('doctor.patient_queue'))

@doctor_bp.route('/radiology-requests')
@login_required
def radiology_requests():
    flash('تم فصل طلبات الأشعة عن الطبيب. للاستعلام، يرجى مراجعة قسم الأشعة أو الاستقبال.', 'warning')
    return redirect(url_for('doctor.patient_queue'))

@doctor_bp.route('/visits')
@login_required
@role_required('doctor', 'admin', 'manager')
def visits():
    """قائمة الزيارات"""
    
    return render_template('doctor/visit_summary.html')

@doctor_bp.route('/medical-records')
@login_required
@role_required('doctor', 'admin', 'manager')
def medical_records():
    """السجلات الطبية"""
    
    return render_template('doctor/patient_details.html')

@doctor_bp.route('/api/patient-search')
@login_required
@role_required_json('doctor', 'admin', 'manager')
def api_patient_search():
    q = request.args.get('q', '').strip()
    query = Patient.query
    if q:
        query = query.filter(
            db.or_(
                Patient.first_name.ilike(f'%{q}%'),
                Patient.last_name.ilike(f'%{q}%'),
                Patient.national_id.ilike(f'%{q}%'),
                Patient.phone.ilike(f'%{q}%')
            )
        )
    patients = query.order_by(Patient.created_at.desc()).limit(10).all()
    results = []
    for p in patients:
        results.append({
            'id': p.id,
            'full_name': p.full_name,
            'national_id': p.national_id,
            'phone': p.phone,
            'visit_count': getattr(p, 'visit_count', 0)
        })
    return jsonify({'patients': results})

@doctor_bp.route('/prescriptions')
@login_required
@role_required('doctor', 'admin', 'manager')
def prescriptions():
    """الوصفات الطبية"""
    
    return render_template('doctor/prescriptions.html')

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
@doctor_bp.route('/dashboard/<int:doctor_id>')
@login_required
@role_required('manager', 'super_admin', 'accountant')
def dashboard_for_doctor(doctor_id):
    """لوحة تحكم لطبيب محدد (عرض إداري)"""
    try:
        target_doctor = db.session.get(User, doctor_id)
        if not target_doctor or target_doctor.role != 'doctor':
            flash('الطبيب غير موجود', 'error')
            return redirect(url_for('main.dashboard'))
        today = date.today()
        week_ago = today - timedelta(days=7)
        today_visits = Visit.query.filter(Visit.doctor_id == doctor_id, Visit.visit_date == today, Visit.status.in_(['OPEN','IN_PROGRESS'])).count()
        pending_visits = Visit.query.filter(Visit.doctor_id == doctor_id, Visit.status == 'OPEN').count()
        completed_today = Visit.query.filter(Visit.doctor_id == doctor_id, Visit.visit_date == today, Visit.status == 'COMPLETED').count()
        weekly_visits = Visit.query.filter(Visit.doctor_id == doctor_id, Visit.visit_date >= week_ago, Visit.status == 'COMPLETED').count()
        prescriptions_today = Prescription.query.join(Visit).filter(Visit.doctor_id == doctor_id, Visit.visit_date == today).count()
        pending_lab_requests = LabRequest.query.join(Visit).filter(Visit.doctor_id == doctor_id, LabRequest.status == 'REQUESTED').count()
        pending_radiology_requests = RadiologyRequest.query.join(Visit).filter(Visit.doctor_id == doctor_id, RadiologyRequest.status == 'REQUESTED').count()
        upcoming_patients = Visit.query.filter(Visit.doctor_id == doctor_id, Visit.visit_date == today, Visit.status.in_(['OPEN','READY'])).order_by(Visit.visit_time).limit(5).all()
        stats = {
            'today_visits': today_visits,
            'pending_visits': pending_visits,
            'completed_today': completed_today,
            'weekly_visits': weekly_visits,
            'prescriptions_today': prescriptions_today,
            'pending_lab_requests': pending_lab_requests,
            'pending_radiology_requests': pending_radiology_requests
        }
        try:
            from decimal import Decimal, ROUND_HALF_UP
            from models.pricing import DoctorPricing
            def compute_fee(v):
                total = Decimal(str(v.total_amount or 0))
                fee = None
                pricing = DoctorPricing.query.filter(DoctorPricing.doctor_id == v.doctor_id, DoctorPricing.department_id == v.department_id, DoctorPricing.is_active == True).order_by(DoctorPricing.effective_from.desc()).first()
                vt = (v.visit_type or '').upper()
                if pricing:
                    if vt in ['FIRST','CONSULTATION'] and pricing.consultation_price:
                        fee = Decimal(str(pricing.consultation_price))
                    elif vt in ['FOLLOW_UP'] and pricing.follow_up_price:
                        fee = Decimal(str(pricing.follow_up_price))
                    elif getattr(v, 'is_emergency', False) and pricing.emergency_price:
                        fee = Decimal(str(pricing.emergency_price))
                if fee is None:
                    fee = (total * Decimal('0.30'))
                if fee > total:
                    fee = total
                return fee.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            month_start = date(today.year, today.month, 1)
            earnings_today = sum(compute_fee(v) for v in Visit.query.filter(Visit.doctor_id == doctor_id, Visit.visit_date == today, Visit.status == 'COMPLETED').all())
            earnings_week = sum(compute_fee(v) for v in Visit.query.filter(Visit.doctor_id == doctor_id, Visit.visit_date >= week_ago, Visit.status == 'COMPLETED').all())
            earnings_month = sum(compute_fee(v) for v in Visit.query.filter(Visit.doctor_id == doctor_id, Visit.visit_date >= month_start, Visit.status == 'COMPLETED').all())
            stats['doctor_earnings_today'] = float(earnings_today)
            stats['doctor_earnings_week'] = float(earnings_week)
            stats['doctor_earnings_month'] = float(earnings_month)
        except Exception:
            stats['doctor_earnings_today'] = 0.0
            stats['doctor_earnings_week'] = 0.0
            stats['doctor_earnings_month'] = 0.0
        return render_template('doctor/dashboard.html', stats=stats, upcoming_patients=upcoming_patients, viewing_doctor=target_doctor)
    except Exception as e:
        logging.error(f"Error in admin view doctor dashboard: {str(e)}")
        flash('حدث خطأ في عرض لوحة الطبيب', 'error')
        return redirect(url_for('main.dashboard'))


@doctor_bp.route('/dental-chart/<int:patient_id>')
@login_required
@role_required('doctor', 'admin', 'manager')
def dental_chart(patient_id):
    """خريطة الأسنان التفاعلية"""
    from models.patient import Patient
    from models.dental import DentalChart, DentalTooth, TOOTH_STATES
    import json

    patient = db.session.get(Patient, patient_id)
    if not patient:
        flash('المريض غير موجود', 'error')
        return redirect(url_for('doctor.patients'))

    upper_right = [{'fdi': f'1{i}', 'x': i*38, 'y': 0} for i in range(8, 0, -1)]
    upper_left = [{'fdi': f'2{i}', 'x': 160 + i*38, 'y': 0} for i in range(1, 9)]
    lower_left = [{'fdi': f'3{i}', 'x': i*38, 'y': 0} for i in range(8, 0, -1)]
    lower_right = [{'fdi': f'4{i}', 'x': 160 + i*38, 'y': 0} for i in range(1, 9)]

    chart = DentalChart.query.filter_by(patient_id=patient_id).order_by(DentalChart.created_at.desc()).first()
    teeth_map = {}
    if chart:
        for tooth in chart.teeth:
            teeth_map[tooth.fdi_number] = {
                'state': tooth.state,
                'surfaces': tooth.surfaces or {},
                'notes': tooth.notes or ''
            }

    def make_tooth_list(layout):
        return [
            {
                'fdi': t['fdi'], 'x': t['x'], 'y': t['y'],
                'state': teeth_map.get(t['fdi'], {}).get('state', 'sound'),
                'color': TOOTH_STATES.get(teeth_map.get(t['fdi'], {}).get('state', 'sound'), {}).get('color', '#10b981')
            }
            for t in layout
        ]

    return render_template('doctor/dental_chart.html',
                           patient=patient, visit_id=None,
                           states=TOOTH_STATES, states_json=json.dumps(TOOTH_STATES),
                           teeth_json=json.dumps(teeth_map),
                           upper_teeth=make_tooth_list(upper_right + upper_left),
                           lower_teeth=make_tooth_list(lower_left + lower_right))


@doctor_bp.route('/dental-chart/save', methods=['POST'])
@login_required
@role_required('doctor', 'admin', 'manager')
def save_dental_chart():
    """حفظ خريطة الأسنان"""
    from models.dental import DentalChart, DentalTooth
    try:
        data = request.get_json() or request.form
        patient_id = int(data.get('patient_id'))
        visit_id = data.get('visit_id')
        teeth_data = data.get('teeth', {})
        notes = data.get('notes', '')

        chart = DentalChart(
            patient_id=patient_id,
            visit_id=int(visit_id) if visit_id else None,
            doctor_id=current_user.id,
            notes=notes
        )
        db.session.add(chart)
        db.session.flush()

        for fdi, info in teeth_data.items():
            if info.get('state') == 'sound' and not info.get('notes') and not info.get('surfaces'):
                continue
            tooth = DentalTooth(
                chart_id=chart.id,
                fdi_number=str(fdi),
                state=info.get('state', 'sound'),
                surfaces=info.get('surfaces') or {},
                notes=info.get('notes', '')
            )
            db.session.add(tooth)

        db.session.commit()
        return jsonify({'success': True, 'chart_id': chart.id})
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error saving dental chart: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500
