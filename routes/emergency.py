"""
مسارات الطوارئ الاحترافية - Professional Emergency Routes
Medical System Professional Emergency Routes
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
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
from app_factory import db
import logging
from datetime import datetime, date, timedelta, timezone
from sqlalchemy import and_, or_, desc, case
import json

emergency_bp = Blueprint('emergency', __name__)

@emergency_bp.route('/')
@login_required
def index():
    return redirect(url_for('emergency.dashboard'))

def _normalize_emergency_status(value):
    v = (value or '').strip().upper()
    if not v:
        return None
    alias = {
        'ACTIVE': 'WAITING',
        'IN_PROGRESS': 'WAITING',
        'RESOLVED': 'COMPLETED',
    }
    v = alias.get(v, v)
    allowed = {
        'WAITING',
        'TRIAGE',
        'RESUSCITATION',
        'TREATMENT',
        'OBSERVATION',
        'TRANSFERRED',
        'DISCHARGED',
        'DECEASED',
        'COMPLETED',
        'CANCELLED',
    }
    return v if v in allowed else v

def _set_emergency_status(emergency, new_status):
    from models.emergency_status_history import EmergencyStatusHistory
    ns = _normalize_emergency_status(new_status)
    if not ns:
        return
    old = getattr(emergency, 'status', None)
    if old == ns:
        return
    db.session.add(EmergencyStatusHistory(
        emergency_id=emergency.id,
        from_status=old,
        to_status=ns,
        changed_by=getattr(current_user, 'id', None),
    ))
    emergency.status = ns


@emergency_bp.route('/reports')
@login_required
def reports():
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))

    try:
        start_raw = (request.args.get('start_date') or '').strip()
        end_raw = (request.args.get('end_date') or '').strip()
        from datetime import datetime as _dt

        try:
            start_date = _dt.strptime(start_raw, '%Y-%m-%d').date() if start_raw else (date.today() - timedelta(days=30))
        except Exception:
            start_date = date.today() - timedelta(days=30)
        try:
            end_date = _dt.strptime(end_raw, '%Y-%m-%d').date() if end_raw else date.today()
        except Exception:
            end_date = date.today()
        if end_date < start_date:
            end_date = start_date

        start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        end_dt = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)

        cases = EmergencyCase.query.filter(EmergencyCase.created_at >= start_dt, EmergencyCase.created_at <= end_dt).order_by(EmergencyCase.created_at.desc()).all()

        by_status = {}
        by_severity = {}
        by_hour = {}
        for c in cases:
            st = (c.status or '').upper()
            sev = (c.severity or '').upper()
            by_status[st] = by_status.get(st, 0) + 1
            by_severity[sev] = by_severity.get(sev, 0) + 1
            try:
                hr = int(c.created_at.strftime('%H'))
                by_hour[hr] = by_hour.get(hr, 0) + 1
            except Exception:
                pass

        top_reasons = {}
        for c in cases:
            txt = (c.chief_complaint or '').strip()
            if not txt:
                continue
            key = ' '.join([p for p in txt.replace('\n', ' ').split(' ') if p][:3]).strip() or txt[:20]
            top_reasons[key] = top_reasons.get(key, 0) + 1
        top_reasons_rows = sorted(top_reasons.items(), key=lambda x: (-x[1], x[0]))[:10]

        stage_avg = {}
        stage_samples = {}
        try:
            from models.emergency_status_history import EmergencyStatusHistory
            ids = [c.id for c in cases]
            history = EmergencyStatusHistory.query.filter(
                EmergencyStatusHistory.emergency_id.in_(ids) if ids else False,
                EmergencyStatusHistory.created_at >= start_dt,
                EmergencyStatusHistory.created_at <= end_dt
            ).order_by(EmergencyStatusHistory.emergency_id.asc(), EmergencyStatusHistory.created_at.asc()).all()
            per_case = {}
            for h in history:
                per_case.setdefault(h.emergency_id, []).append(h)
            for eid, rows in per_case.items():
                for i, h in enumerate(rows):
                    nxt = rows[i + 1] if i + 1 < len(rows) else None
                    if not nxt or not h.created_at or not nxt.created_at:
                        continue
                    dur = (nxt.created_at - h.created_at).total_seconds() / 60.0
                    k = (h.to_status or '').upper()
                    if not k:
                        continue
                    stage_samples[k] = stage_samples.get(k, 0) + 1
                    stage_avg[k] = stage_avg.get(k, 0.0) + float(dur)
            for k in list(stage_avg.keys()):
                stage_avg[k] = round(stage_avg[k] / float(stage_samples.get(k) or 1), 2)
        except Exception:
            stage_avg = {}
            stage_samples = {}

        return render_template(
            'emergency/reports.html',
            start_date=start_date,
            end_date=end_date,
            total=len(cases),
            by_status=by_status,
            by_severity=by_severity,
            by_hour=by_hour,
            top_reasons=top_reasons_rows,
            stage_avg=stage_avg,
            stage_samples=stage_samples
        )
    except Exception as e:
        logging.error(f"Error loading emergency reports: {str(e)}")
        flash('حدث خطأ في تحميل تقارير الطوارئ', 'error')
        return redirect(url_for('emergency.dashboard'))

@emergency_bp.route('/dashboard')
@login_required
def dashboard():
    """لوحة تحكم الطوارئ الاحترافية"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))

    try:
        # إحصائيات متقدمة للطوارئ
        today = date.today()
        week_ago = today - timedelta(days=7)
        
        # حالات الطوارئ اليوم
        today_emergencies = EmergencyCase.query.filter(
            EmergencyCase.created_at >= today
        ).count()
        
        # الحالات النشطة
        active_emergencies = EmergencyCase.query.filter(
            EmergencyCase.status.in_(['WAITING', 'TRIAGE', 'RESUSCITATION', 'TREATMENT', 'OBSERVATION'])
        ).count()
        
        # الحالات المكتملة اليوم
        completed_today = EmergencyCase.query.filter(
            EmergencyCase.status == 'COMPLETED',
            EmergencyCase.completed_at >= today
        ).count()
        
        # الحالات الأسبوع الماضي
        weekly_emergencies = EmergencyCase.query.filter(
            EmergencyCase.created_at >= week_ago,
            EmergencyCase.status == 'COMPLETED'
        ).count()
        
        # الحالات العاجلة
        urgent_cases = EmergencyCase.query.filter(
            EmergencyCase.severity == 'HIGH',
            EmergencyCase.status.in_(['WAITING', 'TRIAGE', 'RESUSCITATION', 'TREATMENT', 'OBSERVATION'])
        ).count()
        
        # الحالات الحرجة
        critical_cases = EmergencyCase.query.filter(
            EmergencyCase.severity == 'CRITICAL',
            EmergencyCase.status.in_(['WAITING', 'TRIAGE', 'RESUSCITATION', 'TREATMENT', 'OBSERVATION'])
        ).count()
        
        # الوصفات الطبية اليوم
        prescriptions_today = 0
        
        # طلبات المختبر المعلقة
        pending_lab_requests = 0
        
        # طلبات الأشعة المعلقة
        pending_radiology_requests = 0
        
        severity_order = case(
            (EmergencyCase.severity == 'CRITICAL', 4),
            (EmergencyCase.severity == 'HIGH', 3),
            (EmergencyCase.severity == 'MODERATE', 2),
            (EmergencyCase.severity == 'LOW', 1),
            else_=0
        )

        # الحالات القادمة (أولوية عالية)
        upcoming_cases = EmergencyCase.query.filter(
            EmergencyCase.status.in_(['WAITING', 'TRIAGE', 'RESUSCITATION', 'TREATMENT', 'OBSERVATION']),
            EmergencyCase.severity.in_(['HIGH', 'CRITICAL'])
        ).order_by(severity_order.desc(), EmergencyCase.created_at).limit(5).all()
        
        # الإحصائيات
        stats = {
            'today_emergencies': today_emergencies,
            'active_emergencies': active_emergencies,
            'completed_today': completed_today,
            'weekly_emergencies': weekly_emergencies,
            'urgent_cases': urgent_cases,
            'critical_cases': critical_cases,
            'prescriptions_today': prescriptions_today,
            'pending_lab_requests': pending_lab_requests,
            'pending_radiology_requests': pending_radiology_requests,
            'time_metrics': get_emergency_time_metrics(),
            'protocols': get_emergency_protocols(),
            'ems_metrics': get_ems_metrics()
        }
        
        return render_template('emergency/dashboard_new.html', 
                             stats=stats, 
                             upcoming_cases=upcoming_cases)
    except Exception as e:
        logging.error(f"Error in emergency dashboard: {str(e)}")
        flash('حدث خطأ في تحميل لوحة التحكم', 'error')
        return redirect(url_for('main.dashboard'))

@emergency_bp.route('/patient-queue')
@login_required
def patient_queue():
    """طابور المرضى في الطوارئ - إدارة متقدمة"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        # جلب الحالات الطارئة مع تفاصيل إضافية
        severity_order = case(
            (EmergencyCase.severity == 'CRITICAL', 4),
            (EmergencyCase.severity == 'HIGH', 3),
            (EmergencyCase.severity == 'MODERATE', 2),
            (EmergencyCase.severity == 'LOW', 1),
            else_=0
        )
        emergencies = EmergencyCase.query.filter(
            EmergencyCase.status.in_(['WAITING', 'TRIAGE', 'RESUSCITATION', 'TREATMENT', 'OBSERVATION'])
        ).order_by(severity_order.desc(), EmergencyCase.created_at).all()
        
        # إحصائيات الطابور
        queue_stats = {
            'total_cases': len(emergencies),
            'triage_cases': len([e for e in emergencies if e.status in ['WAITING', 'TRIAGE', 'RESUSCITATION']]),
            'treatment_cases': len([e for e in emergencies if e.status == 'TREATMENT']),
            'observation_cases': len([e for e in emergencies if e.status == 'OBSERVATION']),
            'urgent_cases': len([e for e in emergencies if e.severity == 'HIGH']),
            'critical_cases': len([e for e in emergencies if e.severity == 'CRITICAL'])
        }
        
        return render_template('emergency/patient_queue.html', 
                             emergencies=emergencies, 
                             queue_stats=queue_stats)
    except Exception as e:
        logging.error(f"Error loading emergency queue: {str(e)}")
        flash('حدث خطأ في تحميل طابور الطوارئ', 'error')
        return redirect(url_for('emergency.dashboard'))

# تم نقل مسار عرض المريض إلى routes/reception.py لتجنب التكرار
# يمكن الوصول إليه عبر /reception/view_patient/<patient_id> مع فلترة تلقائية للطوارئ

@emergency_bp.route('/triage')
@login_required
def triage_list():
    """قائمة الفرز"""
    if current_user.role not in ['emergency', 'doctor', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        return redirect(url_for('emergency.patient_queue'))
    except Exception as e:
        logging.error(f"Error loading triage list: {str(e)}")
        flash('حدث خطأ في تحميل قائمة الفرز', 'error')
        return redirect(url_for('emergency.dashboard'))

@emergency_bp.route('/triage/<int:emergency_id>', methods=['GET', 'POST'])
@login_required
def triage(emergency_id):
    """تقييم حالة المريض (Triage)"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        emergency = db.session.get(EmergencyCase, emergency_id)
        if not emergency:
            flash('حالة الطوارئ غير موجودة', 'error')
            return redirect(url_for('emergency.patient_queue'))
        
        visit = emergency.visit or (db.session.get(Visit, emergency.visit_id) if emergency.visit_id else None)

        if request.method == 'POST':
            triage_level = (request.form.get('triage_level') or '').upper().strip()
            priority = (request.form.get('priority') or '').upper().strip()

            severity_map = {
                'RED': 'CRITICAL',
                'YELLOW': 'HIGH',
                'GREEN': 'MODERATE',
                'CRITICAL': 'CRITICAL',
                'URGENT': 'HIGH',
                'HIGH': 'HIGH',
                'NORMAL': 'MODERATE',
                'MODERATE': 'MODERATE',
                'LOW': 'LOW'
            }
            severity = severity_map.get(triage_level) or severity_map.get(priority) or emergency.severity or 'MODERATE'

            vital_signs = None
            vital_signs_raw = request.form.get('vital_signs')
            if vital_signs_raw:
                try:
                    vital_signs = json.loads(vital_signs_raw)
                except Exception:
                    vital_signs = None
            if vital_signs is None:
                vital_signs = {
                    'blood_pressure': request.form.get('blood_pressure'),
                    'heart_rate': request.form.get('heart_rate'),
                    'temperature': request.form.get('temperature'),
                    'oxygen_saturation': request.form.get('oxygen_saturation'),
                    'respiratory_rate': request.form.get('respiratory_rate'),
                    'pain_level': request.form.get('pain_level')
                }

            emergency.severity = severity
            emergency.triage_notes = request.form.get('triage_notes')
            emergency.chief_complaint = request.form.get('chief_complaint') or emergency.chief_complaint
            try:
                emergency.vital_signs = json.dumps(vital_signs, ensure_ascii=False)
            except Exception:
                pass

            if triage_level in ['RED', 'YELLOW', 'GREEN'] and visit is not None:
                visit.triage_level = triage_level
            elif visit is not None and visit.triage_level is None:
                reverse_map = {'CRITICAL': 'RED', 'HIGH': 'YELLOW', 'MODERATE': 'GREEN', 'LOW': 'GREEN'}
                visit.triage_level = reverse_map.get(severity, 'GREEN')

            if emergency.status in ['IN_PROGRESS', 'TRIAGE']:
                _set_emergency_status(emergency, 'TREATMENT')

            db.session.commit()

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True})

            flash('تم تقييم حالة المريض بنجاح', 'success')
            return redirect(url_for('emergency.patient_queue'))

        return render_template('emergency/triage.html', emergency=emergency, visit=visit)
    except Exception as e:
        logging.error(f"Error in triage: {str(e)}")
        flash('حدث خطأ في تقييم حالة المريض', 'error')
        return redirect(url_for('emergency.patient_queue'))

@emergency_bp.route('/treatment/<int:emergency_id>', methods=['GET', 'POST'])
@login_required
def treatment(emergency_id):
    """علاج الطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        emergency = db.session.get(EmergencyCase, emergency_id)
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

@emergency_bp.route('/prescription/<int:emergency_id>', methods=['GET', 'POST'])
@login_required
def prescription(emergency_id):
    """وصفة طبية للطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        emergency = db.session.get(EmergencyCase, emergency_id)
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
        emergency = db.session.get(EmergencyCase, emergency_id)
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
        emergency = db.session.get(EmergencyCase, emergency_id)
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

@emergency_bp.route('/emergency-report/<int:emergency_id>')
@login_required
def emergency_report(emergency_id):
    """تقرير الطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        emergency = db.session.get(EmergencyCase, emergency_id)
        if not emergency:
            flash('حالة الطوارئ غير موجودة', 'error')
            return redirect(url_for('emergency.patient_queue'))
        return render_template('emergency/emergency_report.html', emergency=emergency)
    except Exception as e:
        logging.error(f"Error generating emergency report: {str(e)}")
        flash('حدث خطأ في إنشاء تقرير الطوارئ', 'error')
        return redirect(url_for('emergency.patient_queue'))

@emergency_bp.route('/end-treatment/<int:emergency_id>', methods=['POST'])
@login_required
def end_treatment(emergency_id):
    """إنهاء العلاج في الطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        emergency = db.session.get(EmergencyCase, emergency_id)
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
        except Exception:
            pass
        
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
        emergency = db.session.get(EmergencyCase, emergency_id)
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

@emergency_bp.route('/patient-details/<int:emergency_id>')
@login_required
def patient_details(emergency_id):
    """تفاصيل حالة الطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        emergency = db.session.get(EmergencyCase, emergency_id)
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
            LabRequest.emergency_id == emergency_id
        ).all()
        
        radiology_requests = RadiologyRequest.query.filter(
            RadiologyRequest.emergency_id == emergency_id
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

@emergency_bp.route('/print-emergency-report/<int:emergency_id>')
@login_required
def print_emergency_report(emergency_id):
    """طباعة تقرير الطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        emergency = db.session.get(EmergencyCase, emergency_id)
        if not emergency:
            flash('حالة الطوارئ غير موجودة', 'error')
            return redirect(url_for('emergency.patient_queue'))
        
        return render_template('print/emergency_report.html',
                             emergency=emergency)
    except Exception as e:
        logging.error(f"Error printing emergency report: {str(e)}")
        flash('حدث خطأ في طباعة تقرير الطوارئ', 'error')
        return redirect(url_for('emergency.patient_queue'))

# ==================== الميزات الذكية للطوارئ ====================

def get_emergency_ai_triage():
    """ذكاء اصطناعي لتصنيف الطوارئ"""
    try:
        from models.emergency import EmergencyCase
        from datetime import datetime, timedelta
        
        # تحليل أولويات الحالات
        priority_analysis = {
            'critical': EmergencyCase.query.filter(EmergencyCase.severity == 'CRITICAL').count(),
            'urgent': EmergencyCase.query.filter(EmergencyCase.severity == 'HIGH').count(),
            'normal': EmergencyCase.query.filter(EmergencyCase.severity == 'MODERATE').count(),
            'low': EmergencyCase.query.filter(EmergencyCase.severity == 'LOW').count()
        }
        
        # تحليل أوقات الاستجابة
        response_times = []
        recent_cases = EmergencyCase.query.filter(
            EmergencyCase.created_at >= datetime.now() - timedelta(days=7)
        ).all()
        
        for case in recent_cases:
            end_time = getattr(case, 'treated_at', None) or getattr(case, 'completed_at', None)
            if end_time and case.created_at:
                response_time = (end_time - case.created_at).total_seconds() / 60
                response_times.append(response_time)
        
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        # اقتراحات التحسين
        triage_suggestions = []
        
        if avg_response_time > 30:  # أكثر من 30 دقيقة
            triage_suggestions.append({
                'type': 'response_time',
                'title': 'تحسين أوقات الاستجابة',
                'description': f'متوسط وقت الاستجابة: {avg_response_time:.1f} دقيقة',
                'suggestion': 'تحسين عملية التصنيف لتسريع الاستجابة'
            })
        
        if priority_analysis['critical'] > 5:
            triage_suggestions.append({
                'type': 'critical_cases',
                'title': 'حالات حرجة عالية',
                'description': f'عدد الحالات الحرجة: {priority_analysis["critical"]}',
                'suggestion': 'مراجعة الموارد المتاحة للحالات الحرجة'
            })
        
        return {
            'priority_analysis': priority_analysis,
            'avg_response_time': round(avg_response_time, 2),
            'triage_suggestions': triage_suggestions,
            'efficiency_score': calculate_triage_efficiency(avg_response_time, priority_analysis)
        }
    except Exception as e:
        logging.error(f"Error getting emergency AI triage: {str(e)}")
        return {}

def get_critical_alert_system():
    """نظام التنبيهات الحرجة"""
    try:
        from models.emergency import EmergencyCase
        from datetime import datetime, timedelta
        
        alerts = []
        
        # تنبيهات الحالات الحرجة
        critical_cases = EmergencyCase.query.filter(
            EmergencyCase.severity == 'CRITICAL',
            EmergencyCase.status.in_(['WAITING', 'TRIAGE', 'RESUSCITATION', 'TREATMENT'])
        ).count()
        
        if critical_cases > 0:
            alerts.append({
                'type': 'critical',
                'title': 'حالات حرجة',
                'message': f'يوجد {critical_cases} حالة حرجة تحتاج انتباه فوري',
                'priority': 'high',
                'action': 'مراجعة فورية'
            })
        
        # تنبيهات أوقات الانتظار الطويلة
        long_waiting = EmergencyCase.query.filter(
            EmergencyCase.status == 'WAITING',
            EmergencyCase.created_at < datetime.now() - timedelta(minutes=30)
        ).count()
        
        if long_waiting > 0:
            alerts.append({
                'type': 'waiting_time',
                'title': 'انتظار طويل',
                'message': f'يوجد {long_waiting} حالة تنتظر أكثر من 30 دقيقة',
                'priority': 'medium',
                'action': 'مراجعة الطابور'
            })
        
        # تنبيهات الموارد
        active_cases = EmergencyCase.query.filter(
            EmergencyCase.status.in_(['WAITING', 'TRIAGE', 'RESUSCITATION', 'TREATMENT', 'OBSERVATION'])
        ).count()
        
        if active_cases > 20:
            alerts.append({
                'type': 'resource_usage',
                'title': 'استخدام الموارد',
                'message': f'عدد الحالات النشطة: {active_cases} - قريب من السعة القصوى',
                'priority': 'medium',
                'action': 'مراجعة الموارد'
            })
        
        return alerts
    except Exception as e:
        logging.error(f"Error getting critical alert system: {str(e)}")
        return []

def get_emergency_workflow_ai():
    """ذكاء اصطناعي لسير عمل الطوارئ"""
    try:
        from models.emergency import EmergencyCase
        from models.visit import Visit
        from datetime import datetime, timedelta
        
        # تحليل مراحل العلاج
        workflow_analysis = {
            'waiting': EmergencyCase.query.filter(EmergencyCase.status == 'WAITING').count(),
            'triage': EmergencyCase.query.filter(EmergencyCase.status == 'TRIAGE').count(),
            'resuscitation': EmergencyCase.query.filter(EmergencyCase.status == 'RESUSCITATION').count(),
            'treatment': EmergencyCase.query.filter(EmergencyCase.status == 'TREATMENT').count(),
            'observation': EmergencyCase.query.filter(EmergencyCase.status == 'OBSERVATION').count(),
            'completed': EmergencyCase.query.filter(EmergencyCase.status == 'COMPLETED').count()
        }
        
        # تحليل أوقات المراحل
        stage_times = []
        completed_cases = EmergencyCase.query.filter(
            EmergencyCase.status == 'COMPLETED',
            EmergencyCase.completed_at >= datetime.now() - timedelta(days=7)
        ).all()
        
        for case in completed_cases:
            end_time = getattr(case, 'treated_at', None) or getattr(case, 'completed_at', None)
            if end_time and case.created_at:
                total_time = (end_time - case.created_at).total_seconds() / 60
                stage_times.append(total_time)
        
        avg_total_time = sum(stage_times) / len(stage_times) if stage_times else 0
        
        # اقتراحات التحسين
        workflow_suggestions = []
        
        if workflow_analysis['triage'] > 10:
            workflow_suggestions.append({
                'type': 'triage_bottleneck',
                'title': 'عنق الزجاجة في التصنيف',
                'description': f'عدد الحالات في التصنيف: {workflow_analysis["triage"]}',
                'suggestion': 'زيادة الموارد في مرحلة التصنيف'
            })
        
        if avg_total_time > 60:  # أكثر من ساعة
            workflow_suggestions.append({
                'type': 'total_time',
                'title': 'تحسين الوقت الإجمالي',
                'description': f'متوسط الوقت الإجمالي: {avg_total_time:.1f} دقيقة',
                'suggestion': 'تحسين سير العمل لتقليل الوقت الإجمالي'
            })
        
        return {
            'workflow_analysis': workflow_analysis,
            'avg_total_time': round(avg_total_time, 2),
            'workflow_suggestions': workflow_suggestions,
            'efficiency_score': calculate_workflow_efficiency(workflow_analysis, avg_total_time)
        }
    except Exception as e:
        logging.error(f"Error getting emergency workflow AI: {str(e)}")
        return {}

def get_patient_vital_monitoring():
    """مراقبة العلامات الحيوية للمرضى"""
    try:
        from models.emergency import EmergencyCase
        from models.visit import Visit
        from datetime import datetime, timedelta
        
        # تحليل العلامات الحيوية
        vital_signs_analysis = {
            'normal': 0,
            'abnormal': 0,
            'critical': 0
        }
        
        # تحليل الحالات حسب العلامات الحيوية
        recent_cases = EmergencyCase.query.filter(
            EmergencyCase.created_at >= datetime.now() - timedelta(days=7)
        ).all()
        
        for case in recent_cases:
            if case.vital_signs:
                # تحليل مبسط للعلامات الحيوية
                vital_data = case.vital_signs
                if 'critical' in str(vital_data).lower():
                    vital_signs_analysis['critical'] += 1
                elif 'abnormal' in str(vital_data).lower():
                    vital_signs_analysis['abnormal'] += 1
                else:
                    vital_signs_analysis['normal'] += 1
        
        # توصيات المراقبة
        monitoring_recommendations = []
        
        if vital_signs_analysis['critical'] > 0:
            monitoring_recommendations.append({
                'type': 'critical_vitals',
                'title': 'علامات حيوية حرجة',
                'description': f'عدد الحالات بعلامات حرجة: {vital_signs_analysis["critical"]}',
                'suggestion': 'مراقبة مستمرة للحالات الحرجة'
            })
        
        if vital_signs_analysis['abnormal'] > 5:
            monitoring_recommendations.append({
                'type': 'abnormal_vitals',
                'title': 'علامات حيوية غير طبيعية',
                'description': f'عدد الحالات بعلامات غير طبيعية: {vital_signs_analysis["abnormal"]}',
                'suggestion': 'مراجعة بروتوكولات المراقبة'
            })
        
        return {
            'vital_signs_analysis': vital_signs_analysis,
            'monitoring_recommendations': monitoring_recommendations,
            'total_cases_monitored': sum(vital_signs_analysis.values())
        }
    except Exception as e:
        logging.error(f"Error getting patient vital monitoring: {str(e)}")
        return {}

def get_emergency_resource_management():
    """إدارة موارد الطوارئ"""
    try:
        from models.emergency import EmergencyCase
        from models.user import User
        from datetime import datetime, timedelta
        
        # تحليل الموارد المتاحة
        total_staff = User.query.filter(User.role == 'emergency').count()
        active_staff = User.query.filter(
            User.role == 'emergency',
            User.last_login >= datetime.now() - timedelta(hours=24)
        ).count()
        
        # تحليل الأحمال
        today = datetime.now().date()
        today_cases = EmergencyCase.query.filter(
            EmergencyCase.created_at >= today
        ).count()
        
        # تحليل الكفاءة
        efficiency_score = (active_staff / total_staff * 100) if total_staff > 0 else 0
        
        # توصيات إدارة الموارد
        resource_recommendations = []
        
        if efficiency_score < 70:
            resource_recommendations.append({
                'type': 'staff_efficiency',
                'title': 'كفاءة الموظفين',
                'description': f'معدل كفاءة الموظفين: {efficiency_score:.1f}%',
                'suggestion': 'تحسين مشاركة الموظفين أو إضافة موارد'
            })
        
        if today_cases > 30:
            resource_recommendations.append({
                'type': 'workload',
                'title': 'عبء العمل',
                'description': f'عدد الحالات اليوم: {today_cases}',
                'suggestion': 'مراجعة توزيع الأحمال أو إضافة موارد'
            })
        
        return {
            'total_staff': total_staff,
            'active_staff': active_staff,
            'today_cases': today_cases,
            'efficiency_score': round(efficiency_score, 2),
            'resource_recommendations': resource_recommendations
        }
    except Exception as e:
        logging.error(f"Error getting emergency resource management: {str(e)}")
        return {}

def get_trauma_protocols():
    """بروتوكولات الصدمات"""
    try:
        from models.emergency import EmergencyCase
        from datetime import datetime, timedelta
        
        # تحليل أنواع الصدمات
        trauma_analysis = {
            'trauma_cases': 0,
            'medical_emergencies': 0,
            'surgical_emergencies': 0,
            'other': 0
        }
        
        # تحليل الحالات الحديثة
        recent_cases = EmergencyCase.query.filter(
            EmergencyCase.created_at >= datetime.now() - timedelta(days=30)
        ).all()
        
        for case in recent_cases:
            if case.chief_complaint:
                complaint = case.chief_complaint.lower()
                if any(word in complaint for word in ['حادث', 'سقوط', 'ضربة', 'جرح']):
                    trauma_analysis['trauma_cases'] += 1
                elif any(word in complaint for word in ['ألم', 'صدر', 'قلب', 'تنفس']):
                    trauma_analysis['medical_emergencies'] += 1
                elif any(word in complaint for word in ['جراحة', 'عملية', 'بطن']):
                    trauma_analysis['surgical_emergencies'] += 1
                else:
                    trauma_analysis['other'] += 1
        
        # توصيات البروتوكولات
        protocol_recommendations = []
        
        if trauma_analysis['trauma_cases'] > 10:
            protocol_recommendations.append({
                'type': 'trauma_protocol',
                'title': 'بروتوكول الصدمات',
                'description': f'عدد حالات الصدمات: {trauma_analysis["trauma_cases"]}',
                'suggestion': 'مراجعة بروتوكولات الصدمات وتدريب الفريق'
            })
        
        if trauma_analysis['medical_emergencies'] > 15:
            protocol_recommendations.append({
                'type': 'medical_protocol',
                'title': 'بروتوكول الطوارئ الطبية',
                'description': f'عدد الطوارئ الطبية: {trauma_analysis["medical_emergencies"]}',
                'suggestion': 'تحسين بروتوكولات الطوارئ الطبية'
            })
        
        return {
            'trauma_analysis': trauma_analysis,
            'protocol_recommendations': protocol_recommendations,
            'total_cases_analyzed': sum(trauma_analysis.values())
        }
    except Exception as e:
        logging.error(f"Error getting trauma protocols: {str(e)}")
        return {}

def get_emergency_analytics():
    """تحليلات الطوارئ"""
    try:
        from models.emergency import EmergencyCase
        from models.medication import Prescription
        from models.lab_request import LabRequest
        from models.radiology_request import RadiologyRequest
        from datetime import datetime, timedelta
        
        # تحليل الأداء
        total_cases = EmergencyCase.query.count()
        completed_cases = EmergencyCase.query.filter(EmergencyCase.status == 'COMPLETED').count()
        completion_rate = (completed_cases / total_cases * 100) if total_cases > 0 else 0
        
        # تحليل الأوقات
        avg_treatment_time = db.session.query(func.avg(
            func.extract('epoch', EmergencyCase.completed_at - EmergencyCase.created_at) / 60
        )).filter(
            EmergencyCase.status == 'COMPLETED',
            EmergencyCase.completed_at.isnot(None)
        ).scalar() or 0
        
        # تحليل الموارد
        prescriptions_count = Prescription.query.join(EmergencyCase).count()
        lab_requests_count = LabRequest.query.join(EmergencyCase).count()
        radiology_requests_count = RadiologyRequest.query.join(EmergencyCase).count()
        
        return {
            'completion_rate': round(completion_rate, 2),
            'avg_treatment_time': round(avg_treatment_time, 2),
            'prescriptions_count': prescriptions_count,
            'lab_requests_count': lab_requests_count,
            'radiology_requests_count': radiology_requests_count,
            'performance_score': calculate_emergency_performance_score(completion_rate, avg_treatment_time)
        }
    except Exception as e:
        logging.error(f"Error getting emergency analytics: {str(e)}")
        return {}

def get_smart_emergency_recommendations():
    """التوصيات الذكية للطوارئ"""
    try:
        from models.emergency import EmergencyCase
        from models.user import User
        from datetime import datetime, timedelta
        
        recommendations = []
        
        # تحليل النمو
        week_ago = datetime.now().date() - timedelta(days=7)
        cases_this_week = EmergencyCase.query.filter(
            EmergencyCase.created_at >= week_ago
        ).count()
        
        cases_last_week = EmergencyCase.query.filter(
            EmergencyCase.created_at >= week_ago - timedelta(days=7),
            EmergencyCase.created_at < week_ago
        ).count()
        
        growth_rate = ((cases_this_week - cases_last_week) / cases_last_week * 100) if cases_last_week > 0 else 0
        
        if growth_rate > 20:
            recommendations.append({
                'type': 'growth',
                'title': 'نمو سريع في الطوارئ',
                'description': f'زيادة {growth_rate:.1f}% في حالات الطوارئ',
                'suggestion': 'مراجعة الموارد والاستعداد للزيادة'
            })
        
        # تحليل الكفاءة
        avg_response_time = db.session.query(func.avg(
            func.extract('epoch', EmergencyCase.completed_at - EmergencyCase.created_at) / 60
        )).filter(
            EmergencyCase.status == 'COMPLETED',
            EmergencyCase.completed_at.isnot(None)
        ).scalar() or 0
        
        if avg_response_time > 45:
            recommendations.append({
                'type': 'efficiency',
                'title': 'تحسين الكفاءة',
                'description': f'متوسط وقت الاستجابة: {avg_response_time:.1f} دقيقة',
                'suggestion': 'تحسين العمليات لتسريع الاستجابة'
            })
        
        # تحليل الموظفين
        active_emergency_staff = User.query.filter(
            User.role == 'emergency',
            User.last_login >= datetime.now() - timedelta(days=7)
        ).count()
        
        total_emergency_staff = User.query.filter(User.role == 'emergency').count()
        
        if active_emergency_staff < total_emergency_staff * 0.8:
            recommendations.append({
                'type': 'staff_engagement',
                'title': 'مشاركة الموظفين',
                'description': f'فقط {active_emergency_staff} من {total_emergency_staff} موظف نشط',
                'suggestion': 'تحفيز الموظفين أو إعادة توزيع المهام'
            })
        
        return recommendations
    except Exception as e:
        logging.error(f"Error getting smart emergency recommendations: {str(e)}")
        return []

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

def get_emergency_time_metrics():
    try:
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=7)
        rows = EmergencyCase.query.filter(EmergencyCase.created_at >= start).all()
        if not rows:
            return {'avg_time_to_triage': 0, 'avg_time_to_treatment': 0, 'avg_length_of_stay': 0}
        triage_times = []
        treatment_times = []
        los_times = []
        for c in rows:
            created = c.created_at
            if not created:
                continue
            updated = c.updated_at or created
            if c.status in ['TRIAGE', 'RESUSCITATION', 'TREATMENT', 'OBSERVATION', 'COMPLETED']:
                triage_times.append((updated - created).total_seconds() / 60)
            if c.status in ['TREATMENT', 'OBSERVATION', 'COMPLETED']:
                treatment_times.append((updated - created).total_seconds() / 60)
            if c.completed_at:
                los_times.append((c.completed_at - created).total_seconds() / 60)
        def _avg(vals):
            return round(sum(vals) / len(vals), 2) if vals else 0
        return {
            'avg_time_to_triage': _avg(triage_times),
            'avg_time_to_treatment': _avg(treatment_times),
            'avg_length_of_stay': _avg(los_times)
        }
    except Exception:
        return {}

def get_emergency_protocols():
    try:
        protocols = [
            {'id': 'stroke', 'title': 'بروتوكول السكتة الدماغية', 'keywords': ['ضعف', 'شلل', 'سكتة', 'stroke'], 'steps': ['تقييم FAST', 'CT عاجل', 'تفعيل فريق السكتة']},
            {'id': 'mi', 'title': 'بروتوكول MI', 'keywords': ['صدر', 'ألم صدري', 'mi', 'heart'], 'steps': ['ECG خلال 10 دقائق', 'مخبر قلب', 'تحضير قسطرة']},
            {'id': 'trauma', 'title': 'بروتوكول الإصابات', 'keywords': ['حادث', 'سقوط', 'جرح', 'trauma'], 'steps': ['ABC', 'تصوير سريع', 'تحضير غرفة العمليات']}
        ]
        active = EmergencyCase.query.filter(
            EmergencyCase.status.in_(['WAITING', 'TRIAGE', 'RESUSCITATION', 'TREATMENT', 'OBSERVATION'])
        ).order_by(EmergencyCase.created_at.desc()).limit(50).all()
        matched = []
        for c in active:
            complaint = (c.chief_complaint or '').lower()
            for p in protocols:
                if any(k in complaint for k in p['keywords']):
                    matched.append(p)
                    break
        return matched[:6]
    except Exception:
        return []

def get_ems_metrics():
    try:
        start = datetime.now(timezone.utc) - timedelta(days=7)
        ems_cases = EmergencyCase.query.filter(
            EmergencyCase.case_number.like('EMS-%'),
            EmergencyCase.created_at >= start
        ).count()
        return {'ems_cases_7d': int(ems_cases or 0)}
    except Exception:
        return {}

# دوال مساعدة
def calculate_triage_efficiency(avg_response_time, priority_analysis):
    """حساب كفاءة التصنيف"""
    # نقاط وقت الاستجابة (كلما قل الوقت كلما زادت النقاط)
    response_score = max(0, 100 - (avg_response_time / 10))
    
    # نقاط الأولوية (توازن في الأولويات)
    critical_ratio = priority_analysis['critical'] / sum(priority_analysis.values()) if sum(priority_analysis.values()) > 0 else 0
    priority_score = 100 - (critical_ratio * 50)  # تقليل النقاط مع زيادة الحالات الحرجة
    
    return (response_score + priority_score) / 2

def calculate_workflow_efficiency(workflow_analysis, avg_total_time):
    """حساب كفاءة سير العمل"""
    # نقاط التوزيع (توازن في المراحل)
    total_cases = sum(workflow_analysis.values())
    if total_cases == 0:
        return 0
    
    distribution_score = 100 - abs(workflow_analysis['triage'] - workflow_analysis['treatment']) / total_cases * 100
    
    # نقاط الوقت (كلما قل الوقت كلما زادت النقاط)
    time_score = max(0, 100 - (avg_total_time / 2))
    
    return (distribution_score + time_score) / 2

def calculate_emergency_performance_score(completion_rate, avg_treatment_time):
    """حساب نقاط أداء الطوارئ"""
    # نقاط الإنجاز
    completion_score = completion_rate
    
    # نقاط الوقت (كلما قل الوقت كلما زادت النقاط)
    time_score = max(0, 100 - (avg_treatment_time / 2))
    
    return (completion_score + time_score) / 2

@emergency_bp.route('/cases')
@login_required
def list_emergency_cases():
    """حالات الطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        query = EmergencyCase.query
        search = request.args.get('search')
        priority = request.args.get('priority')
        status = request.args.get('status')
        doctor_id = request.args.get('doctor_id')
        today_only = request.args.get('today') == 'true'
        page = request.args.get('page', 1, type=int)
        per_page = 12

        if search:
            query = query.join(Patient).filter(
                or_(
                    EmergencyCase.chief_complaint.ilike(f"%{search}%"),
                    Patient.name.ilike(f"%{search}%")
                )
            )

        if priority:
            severity_map = {
                'low': 'LOW',
                'medium': 'MODERATE',
                'high': 'HIGH',
                'critical': 'CRITICAL'
            }
            query = query.filter(EmergencyCase.severity == severity_map.get(priority, EmergencyCase.severity))

        if status:
            if status == 'active':
                query = query.filter(EmergencyCase.status != 'COMPLETED')
            elif status == 'resolved':
                query = query.filter(EmergencyCase.status == 'COMPLETED')
            else:
                query = query.filter(EmergencyCase.status == status.upper())

        if doctor_id:
            try:
                did = int(doctor_id)
                query = query.join(Visit, EmergencyCase.visit_id == Visit.id).filter(Visit.doctor_id == did)
            except Exception:
                pass

        if today_only:
            today = date.today()
            start = datetime.combine(today, datetime.min.time())
            end = datetime.combine(today, datetime.max.time())
            query = query.filter(EmergencyCase.created_at >= start, EmergencyCase.created_at <= end)

        query = query.order_by(desc(EmergencyCase.created_at))
        emergency_cases = query.paginate(page=page, per_page=per_page, error_out=False)

        for emergency in emergency_cases.items:
            emergency.emergency_date = emergency.created_at
            emergency.emergency_time = emergency.created_at
            emergency.doctor = emergency.visit.doctor if emergency.visit and emergency.visit.doctor else None
            try:
                emergency.vital_signs = json.loads(emergency.vital_signs) if emergency.vital_signs else None
            except Exception:
                emergency.vital_signs = None

        total_emergencies = EmergencyCase.query.count()
        today_emergencies = EmergencyCase.query.filter(
            EmergencyCase.created_at >= datetime.combine(date.today(), datetime.min.time())
        ).count()
        critical_emergencies = EmergencyCase.query.filter(EmergencyCase.severity == 'CRITICAL').count()
        active_emergencies = EmergencyCase.query.filter(EmergencyCase.status != 'COMPLETED').count()

        doctors = User.query.filter_by(role='doctor').all()

        return render_template(
            'emergency/list.html',
            emergency_cases=emergency_cases,
            total_emergencies=total_emergencies,
            today_emergencies=today_emergencies,
            critical_emergencies=critical_emergencies,
            active_emergencies=active_emergencies,
            doctors=doctors
        )
    except Exception as e:
        logging.error(f"Error loading emergency cases: {str(e)}")
        flash('حدث خطأ في تحميل حالات الطوارئ', 'error')
        return redirect(url_for('emergency.dashboard'))

@emergency_bp.route('/cases/<int:id>')
@login_required
def view_emergency_case(id):
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    try:
        emergency = db.session.get(EmergencyCase, id)
        if not emergency:
            flash('حالة الطوارئ غير موجودة', 'error')
            return redirect(url_for('emergency.list_emergency_cases'))
        emergency.emergency_date = emergency.created_at
        emergency.emergency_time = emergency.created_at
        emergency.doctor = emergency.visit.doctor if emergency.visit and emergency.visit.doctor else None
        try:
            emergency.vital_signs = json.loads(emergency.vital_signs) if emergency.vital_signs else None
        except Exception:
            emergency.vital_signs = None
        history = []
        timeline = []
        try:
            from models.emergency_status_history import EmergencyStatusHistory
            history = EmergencyStatusHistory.query.filter_by(emergency_id=emergency.id).order_by(EmergencyStatusHistory.created_at.asc()).all()
            for i, h in enumerate(history):
                next_h = history[i + 1] if i + 1 < len(history) else None
                dur_min = None
                if next_h and h.created_at and next_h.created_at:
                    dur_min = int((next_h.created_at - h.created_at).total_seconds() // 60)
                timeline.append({'item': h, 'duration_minutes': dur_min})
        except Exception:
            timeline = []

        return render_template('emergency/view.html', emergency=emergency, status_timeline=timeline)
    except Exception as e:
        logging.error(f"Error viewing emergency case: {str(e)}")
        flash('حدث خطأ في عرض حالة الطوارئ', 'error')
        return redirect(url_for('emergency.list_emergency_cases'))

@emergency_bp.route('/cases/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_emergency_case(id):
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    try:
        emergency = db.session.get(EmergencyCase, id)
        if not emergency:
            flash('حالة الطوارئ غير موجودة', 'error')
            return redirect(url_for('emergency.list_emergency_cases'))
        if request.method == 'POST':
            emergency.patient_id = request.form.get('patient_id', type=int) or emergency.patient_id
            emergency_date = request.form.get('emergency_date')
            emergency_time = request.form.get('emergency_time')
            if emergency_date and emergency_time:
                try:
                    dt = datetime.strptime(f"{emergency_date} {emergency_time}", "%Y-%m-%d %H:%M")
                    emergency.created_at = dt
                except Exception:
                    pass
            priority_val = request.form.get('priority')
            severity_map = {
                'low': 'LOW',
                'medium': 'MODERATE',
                'high': 'HIGH',
                'critical': 'CRITICAL'
            }
            emergency.severity = severity_map.get(priority_val, emergency.severity)
            status_val = request.form.get('status')
            if status_val:
                mapped = status_val.upper() if status_val in ['active', 'resolved', 'transferred', 'cancelled'] else status_val
                _set_emergency_status(emergency, mapped)
                if status_val == 'resolved':
                    emergency.completed_at = datetime.now(timezone.utc)
            emergency.chief_complaint = request.form.get('chief_complaint') or emergency.chief_complaint
            emergency.symptoms = request.form.get('symptoms') or emergency.symptoms
            vs = {
                'bp_systolic': request.form.get('vital_signs_bp_systolic'),
                'bp_diastolic': request.form.get('vital_signs_bp_diastolic'),
                'heart_rate': request.form.get('vital_signs_heart_rate'),
                'temperature': request.form.get('vital_signs_temperature'),
                'oxygen_saturation': request.form.get('vital_signs_oxygen_saturation')
            }
            try:
                emergency.vital_signs = json.dumps(vs)
            except Exception:
                pass
            emergency.diagnosis = request.form.get('initial_assessment') or emergency.diagnosis
            emergency.treatment_plan = request.form.get('treatment_given') or emergency.treatment_plan
            emergency.notes = request.form.get('notes') or emergency.notes
            follow_up_required = True if request.form.get('follow_up_required') else False
            emergency.follow_up_required = follow_up_required if hasattr(emergency, 'follow_up_required') else getattr(emergency, 'follow_up_required', False)
            follow_up_date = request.form.get('follow_up_date')
            if follow_up_date and hasattr(emergency, 'follow_up_date'):
                try:
                    emergency.follow_up_date = datetime.strptime(follow_up_date, "%Y-%m-%d").date()
                except Exception:
                    pass
            db.session.commit()
            flash('تم تحديث حالة الطوارئ بنجاح', 'success')
            return redirect(url_for('emergency.view_emergency_case', id=emergency.id))
        doctors = User.query.filter_by(role='doctor').all()
        patients = Patient.query.all()
        emergency.emergency_date = emergency.created_at
        emergency.emergency_time = emergency.created_at
        emergency.doctor = emergency.visit.doctor if emergency.visit and emergency.visit.doctor else None
        try:
            emergency.vital_signs = json.loads(emergency.vital_signs) if emergency.vital_signs else None
        except Exception:
            emergency.vital_signs = None
        return render_template('emergency/edit.html', emergency=emergency, doctors=doctors, patients=patients)
    except Exception as e:
        logging.error(f"Error editing emergency case: {str(e)}")
        flash('حدث خطأ في تعديل حالة الطوارئ', 'error')
        return redirect(url_for('emergency.list_emergency_cases'))

@emergency_bp.route('/cases/<int:id>/resolve', methods=['POST'])
@login_required
def resolve_emergency_case(id):
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    try:
        emergency = db.session.get(EmergencyCase, id)
        if not emergency:
            flash('حالة الطوارئ غير موجودة', 'error')
            return redirect(url_for('emergency.list_emergency_cases'))
        _set_emergency_status(emergency, 'COMPLETED')
        emergency.completed_at = datetime.now(timezone.utc)
        db.session.commit()
        flash('تم حل الحالة بنجاح', 'success')
        return redirect(url_for('emergency.list_emergency_cases'))
    except Exception as e:
        logging.error(f"Error resolving emergency case: {str(e)}")
        flash('حدث خطأ في حل حالة الطوارئ', 'error')
        return redirect(url_for('emergency.list_emergency_cases'))

@emergency_bp.route('/cases/create', methods=['POST'])
@login_required
def create_emergency_case():
    if current_user.role not in ['emergency', 'admin', 'manager']:
        return jsonify({'success': False, 'message': 'غير مصرح'}), 403
    try:
        data = request.get_json() if request.is_json else request.form
        patient_id = data.get('patient_id')
        if not patient_id:
            return jsonify({'success': False, 'message': 'رقم المريض مطلوب'}), 400
        try:
            patient_id = int(patient_id)
        except Exception:
            return jsonify({'success': False, 'message': 'رقم المريض غير صحيح'}), 400
        patient = db.session.get(Patient, patient_id)
        if not patient:
            return jsonify({'success': False, 'message': 'المريض غير موجود'}), 404

        emergency_department_id = None
        try:
            from models.department import Department
            departments = Department.query.filter_by(is_active=True).all()
            for d in departments:
                if d.get_type() == 'emergency':
                    emergency_department_id = d.id
                    break
        except Exception:
            emergency_department_id = None

        visit = Visit(
            patient_id=patient_id,
            department_id=emergency_department_id,
            status='OPEN',
            visit_type='EMERGENCY',
            is_emergency=True,
            created_by=current_user.id
        )
        db.session.add(visit)
        db.session.flush()
        case_number = f"EC-{visit.id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        emergency = EmergencyCase(
            patient_id=patient_id,
            visit_id=visit.id,
            case_number=case_number,
            chief_complaint=data.get('case_description') or '',
            severity=(data.get('priority') or 'MODERATE').upper(),
            status='WAITING'
        )
        db.session.add(emergency)
        db.session.flush()
        try:
            from models.emergency_status_history import EmergencyStatusHistory
            db.session.add(EmergencyStatusHistory(emergency_id=emergency.id, from_status=None, to_status='WAITING', changed_by=current_user.id))
        except Exception:
            pass
        try:
            from models.queue_management import QueueManagement
            if visit.department_id:
                qm = QueueManagement(
                    department_id=visit.department_id,
                    patient_id=patient_id,
                    visit_id=visit.id,
                    queue_number=str(visit.id),
                    priority_level='urgent',
                    status='waiting',
                    is_emergency=True
                )
                db.session.add(qm)
        except Exception:
            pass
        try:
            from models.patient_visit_counter import PatientVisitCounter
            pvc = PatientVisitCounter.query.filter_by(patient_id=patient_id).first()
            if not pvc:
                pvc = PatientVisitCounter(patient_id=patient_id, visit_count=0)
                db.session.add(pvc)
            pvc.visit_count = (pvc.visit_count or 0) + 1
            from datetime import datetime as _dt, timezone
            pvc.last_visit_at = _dt.now(timezone.utc)
        except Exception:
            pass
        db.session.commit()
        return jsonify({'success': True, 'visit_id': visit.id, 'case_id': emergency.id}), 200
    except Exception as e:
        logging.error(f"Create emergency case error: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'message': 'تعذر إنشاء حالة الطوارئ حالياً'}), 500

@emergency_bp.route('/cases/<int:id>/convert', methods=['POST'])
@login_required
def convert_emergency_case(id):
    if current_user.role not in ['reception', 'super_admin']:
        return jsonify({'success': False, 'message': 'غير مصرح'}), 403
    try:
        emergency = db.session.get(EmergencyCase, id)
        if not emergency:
            return jsonify({'success': False, 'message': 'حالة الطوارئ غير موجودة'}), 404
        visit = emergency.visit
        if not visit:
            return jsonify({'success': False, 'message': 'الزيارة غير موجودة'}), 404
        dest = request.json.get('new_destination') if request.is_json else request.form.get('new_destination')
        if not dest:
            return jsonify({'success': False, 'message': 'الوجهة مطلوبة'}), 400
        dest = str(dest).lower().strip()
        target_department_id = None
        target_doctor_id = visit.doctor_id
        try:
            from models.department import Department
            departments = Department.query.filter_by(is_active=True).all()
            if dest == 'lab':
                for d in departments:
                    if d.get_type() == 'lab':
                        target_department_id = d.id
                        break
            elif dest == 'radiology':
                for d in departments:
                    if d.get_type() == 'radiology':
                        target_department_id = d.id
                        break
            elif dest == 'doctor':
                for d in departments:
                    if d.get_type() == 'general':
                        target_department_id = d.id
                        break
            else:
                return jsonify({'success': False, 'message': 'الوجهة غير صحيحة'}), 400
        except Exception:
            target_department_id = None
        if not target_department_id:
            return jsonify({'success': False, 'message': 'القسم غير موجود'}), 404
        from services.queue_management_service import QueueManagementService
        ok, msg = QueueManagementService().transfer_visit(
            visit.id,
            target_department_id,
            target_doctor_id if dest == 'doctor' else None
        )
        if ok:
            return jsonify({'success': True}), 200
        status = 500
        if msg in {'invalid_department', 'doctor_required'}:
            status = 400
            msg = 'بيانات القسم أو الطبيب غير صحيحة'
        elif msg in {'visit_not_found', 'department_not_found'}:
            status = 404
            msg = 'الزيارة أو القسم غير موجود'
        elif msg == 'cannot_transfer_active_treatment':
            status = 409
            msg = 'لا يمكن تحويل زيارة قيد العلاج'
        elif not msg:
            msg = 'تعذر تحويل الزيارة حالياً'
        return jsonify({'success': False, 'message': msg}), status
    except Exception as e:
        logging.error(f"Convert emergency case outer error: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر تحويل الحالة حالياً'}), 500

@emergency_bp.route('/patients')
@login_required
def patients():
    """مرضى الطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('emergency/patient_queue.html')

@emergency_bp.route('/queue')
@login_required
def queue():
    """طابور الطوارئ"""
    if current_user.role not in ['emergency', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('emergency/patient_queue.html')


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
            except Exception:
                pass
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
            emergency_case.status = 'COMPLETED'
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
        except Exception:
            pass
        db.session.commit()
        return jsonify({'success': True}), 200
    except Exception as e:
        logging.error(f"Complete emergency visit error: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'message': 'تعذر إنهاء الزيارة حالياً'}), 500

