 

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from utils.decorators import role_required
from models.patient import Patient
from models.visit import Visit
from models.medication import Medication
from app_factory import db
import logging
from datetime import datetime, timedelta, timezone, date
import json
from sqlalchemy import func, and_, or_, desc

nurse_bp = Blueprint('nurse', __name__)

@nurse_bp.route('/')
@login_required
def index():
    return redirect(url_for('nurse.dashboard'))

def _accessible_department_ids():
    try:
        from services.access_control_service import AccessControlService
        return AccessControlService.get_accessible_department_ids(current_user)
    except Exception:
        return []

def _nursing_protocols_key():
    return f'nursing_protocols_{current_user.id}'

def _default_nursing_protocols():
    return [
        {'id': 'fall_prevention', 'title': 'منع السقوط', 'steps': ['تقييم عوامل الخطر', 'تأمين السرير', 'مراجعة أدوية الدوخة']},
        {'id': 'pressure_ulcer', 'title': 'منع قرح الفراش', 'steps': ['تغيير الوضعية كل ساعتين', 'فحص الجلد', 'العناية بالتغذية']},
        {'id': 'pain_management', 'title': 'تقييم الألم', 'steps': ['قياس شدة الألم', 'إعطاء المسكنات', 'إعادة التقييم']}
    ]

def _get_nursing_protocols():
    from models.system_config import SystemConfig
    cfg = SystemConfig.query.filter_by(config_key=_nursing_protocols_key()).first()
    if not cfg:
        cfg = SystemConfig(
            config_key=_nursing_protocols_key(),
            config_type='json',
            config_value='[]',
            category='system',
            description='بروتوكولات تمريضية',
            is_system=False,
            is_encrypted=False,
            created_by=getattr(current_user, 'id', None),
            updated_by=getattr(current_user, 'id', None),
        )
        db.session.add(cfg)
        data = _default_nursing_protocols()
        cfg.set_value(data)
        db.session.commit()
        return data
    data = cfg.get_value() if cfg.config_type == 'json' else []
    if not isinstance(data, list) or not data:
        data = _default_nursing_protocols()
        cfg.config_type = 'json'
        cfg.set_value(data)
        cfg.updated_by = getattr(current_user, 'id', None)
        db.session.commit()
    return data

def _save_nursing_protocols(items):
    from models.system_config import SystemConfig
    cfg = SystemConfig.query.filter_by(config_key=_nursing_protocols_key()).first()
    if not cfg:
        cfg = SystemConfig(
            config_key=_nursing_protocols_key(),
            config_type='json',
            config_value='[]',
            category='system',
            description='بروتوكولات تمريضية',
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

@nurse_bp.route('/dashboard')
@login_required
@role_required('nurse', 'admin', 'manager')
def dashboard():
    """لوحة تحكم الممرضة"""
    
    try:
        from models.task_management import Task
        from models.nurse import VitalSigns, MedicationAdministrationLog
        from models.medication import Prescription, PrescriptionItem

        today = datetime.now(timezone.utc).date()
        start_of_today = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
        end_of_today = datetime.combine(today, datetime.max.time(), tzinfo=timezone.utc)

        total_patients = Patient.query.count()
        patients_today = Patient.query.filter(Patient.created_at >= start_of_today).count()

        active_visits_query = Visit.query.filter(
            Visit.status.in_(['OPEN', 'IN_PROGRESS'])
        )
        dept_ids = _accessible_department_ids()
        if dept_ids is not None and dept_ids:
            active_visits_query = active_visits_query.filter(Visit.department_id.in_(dept_ids))

        active_visits = active_visits_query.count()
        active_visits_list = active_visits_query.order_by(desc(Visit.created_at)).limit(20).all()

        today_visits = Visit.query.filter(Visit.visit_date == today).count()
        recent_visits = Visit.query.order_by(desc(Visit.created_at)).limit(20).all()
        
        # الأدوية المطلوبة
        medications_needed = Medication.query.filter(
            Medication.stock_quantity <= Medication.minimum_stock
        ).count()

        open_tasks = Task.query.filter(
            Task.assigned_to == current_user.id,
            Task.status.in_(['pending', 'in_progress'])
        ).order_by(desc(Task.created_at)).limit(10).all()

        vital_due_count = 0
        meds_due_count = 0
        task_items = []

        active_visit_ids = [v.id for v in active_visits_list if getattr(v, 'id', None)]
        active_patient_ids = [v.patient_id for v in active_visits_list if getattr(v, 'patient_id', None)]

        latest_vitals_by_patient = {}
        if active_patient_ids:
            rows = VitalSigns.query.filter(
                VitalSigns.patient_id.in_(active_patient_ids)
            ).order_by(desc(VitalSigns.recorded_at)).all()
            for r in rows:
                if r.patient_id not in latest_vitals_by_patient:
                    latest_vitals_by_patient[r.patient_id] = r

        last_admin_by_item = {}
        if active_visit_ids:
            logs = MedicationAdministrationLog.query.filter(
                MedicationAdministrationLog.visit_id.in_(active_visit_ids)
            ).order_by(desc(MedicationAdministrationLog.administered_at)).limit(300).all()
            for row in logs:
                if row.prescription_item_id and row.prescription_item_id not in last_admin_by_item:
                    last_admin_by_item[row.prescription_item_id] = row

        prescribed_items_by_visit = {}
        if active_visit_ids:
            prescribed = PrescriptionItem.query.join(
                Prescription, PrescriptionItem.prescription_id == Prescription.id
            ).filter(
                Prescription.visit_id.in_(active_visit_ids),
                Prescription.status == 'active'
            ).all()
            for it in prescribed:
                visit_id = getattr(getattr(it, 'prescription', None), 'visit_id', None)
                if not visit_id:
                    continue
                prescribed_items_by_visit.setdefault(visit_id, []).append(it)

        now = datetime.now(timezone.utc)
        vital_due_after = timedelta(hours=4)
        for v in active_visits_list:
            last_vs = latest_vitals_by_patient.get(v.patient_id)
            last_vs_dt = getattr(last_vs, 'recorded_at', None)
            if last_vs_dt and not last_vs_dt.tzinfo:
                last_vs_dt = last_vs_dt.replace(tzinfo=timezone.utc)
            vs_due = (not last_vs_dt) or (now - last_vs_dt > vital_due_after)
            if vs_due:
                vital_due_count += 1
                task_items.append({
                    'type': 'vitals',
                    'title': 'قياس العلامات الحيوية',
                    'visit_id': v.id,
                    'patient_name': v.patient.full_name if getattr(v, 'patient', None) else '',
                    'url': url_for('nurse.vital_signs', visit_id=v.id),
                    'priority': 'high' if getattr(v, 'is_emergency', False) else 'medium'
                })

            items = prescribed_items_by_visit.get(v.id) or []
            unadmin = [it for it in items if it.id not in last_admin_by_item]
            if unadmin:
                meds_due_count += 1
                task_items.append({
                    'type': 'meds',
                    'title': 'تنفيذ أدوية موصوفة',
                    'visit_id': v.id,
                    'patient_name': v.patient.full_name if getattr(v, 'patient', None) else '',
                    'url': url_for('nurse.medication_administration', visit_id=v.id),
                    'priority': 'medium'
                })

        pending_tasks = int(len(open_tasks) + vital_due_count + meds_due_count)

        def _vitals_flags(vs: VitalSigns):
            sys = getattr(vs, 'blood_pressure_systolic', None)
            dia = getattr(vs, 'blood_pressure_diastolic', None)
            hr = getattr(vs, 'heart_rate', None)
            temp = getattr(vs, 'temperature', None)
            spo2 = getattr(vs, 'oxygen_saturation', None)
            rr = getattr(vs, 'respiratory_rate', None)

            critical = False
            abnormal = False

            if sys is not None and sys > 160:
                critical = True
            if hr is not None and hr > 120:
                critical = True
            if temp is not None and temp > 38.5:
                critical = True
            if spo2 is not None and spo2 < 90:
                critical = True

            if sys is not None and sys > 140:
                abnormal = True
            if dia is not None and dia > 90:
                abnormal = True
            if hr is not None and hr > 100:
                abnormal = True
            if temp is not None and temp > 37.5:
                abnormal = True
            if spo2 is not None and spo2 < 94:
                abnormal = True
            if rr is not None and rr > 22:
                abnormal = True

            return abnormal, critical

        patient_name_by_id = {}
        for v in active_visits_list:
            if getattr(v, 'patient_id', None) and v.patient_id not in patient_name_by_id:
                patient_name_by_id[v.patient_id] = v.patient.full_name if getattr(v, 'patient', None) else ''

        vitals_alerts = []
        for pid, vs in (latest_vitals_by_patient or {}).items():
            if not vs:
                continue
            abnormal, critical = _vitals_flags(vs)
            if not abnormal and not critical:
                continue
            recorded_at = getattr(vs, 'recorded_at', None)
            if recorded_at and not recorded_at.tzinfo:
                recorded_at = recorded_at.replace(tzinfo=timezone.utc)
            if not recorded_at:
                continue
            age_minutes = (now - recorded_at).total_seconds() / 60.0
            if critical and age_minutes >= 15:
                vitals_alerts.append({
                    'severity': 'critical',
                    'patient_id': pid,
                    'patient_name': patient_name_by_id.get(pid) or f'#{pid}',
                    'recorded_at': recorded_at,
                    'url': url_for('nurse.vital_signs', patient_id=pid)
                })
            elif abnormal and age_minutes >= 60:
                vitals_alerts.append({
                    'severity': 'abnormal',
                    'patient_id': pid,
                    'patient_name': patient_name_by_id.get(pid) or f'#{pid}',
                    'recorded_at': recorded_at,
                    'url': url_for('nurse.vital_signs', patient_id=pid)
                })

        overdue_tasks_q = Task.query.filter(
            Task.assigned_to == current_user.id,
            Task.due_date.isnot(None),
            Task.due_date < now,
            Task.status.in_(['pending', 'in_progress', 'on_hold'])
        )
        overdue_tasks_count = overdue_tasks_q.count()
        overdue_important = overdue_tasks_q.filter(Task.priority.in_(['high', 'urgent'])).order_by(Task.due_date.asc()).limit(10).all()
        overdue_any = overdue_tasks_q.order_by(Task.due_date.asc()).limit(10).all()

        safety_alerts = {
            'vitals_alerts': vitals_alerts[:10],
            'vitals_alerts_count': len(vitals_alerts),
            'overdue_tasks_count': int(overdue_tasks_count or 0),
            'overdue_important': overdue_important,
            'overdue_any': overdue_any
        }
        
        # الميزات الذكية
        smart_analytics = get_nursing_smart_analytics()
        patient_care_optimization = get_patient_care_optimization()
        vital_signs_monitoring = get_vital_signs_monitoring()
        medication_management = get_medication_management()
        workflow_automation = get_nursing_workflow_automation()
        predictive_insights = get_nursing_predictive_insights()
        smart_recommendations = get_nursing_smart_recommendations()
        quality_indicators = get_nursing_quality_indicators()
        nursing_protocols = _get_nursing_protocols()
        workload_prediction = get_nursing_workload_prediction()
        
        stats = {
            'patients_today': patients_today,
            'active_visits': active_visits,
            'medications_needed': medications_needed,
            'pending_tasks': pending_tasks,
            'smart_analytics': smart_analytics,
            'patient_care_optimization': patient_care_optimization,
            'vital_signs_monitoring': vital_signs_monitoring,
            'medication_management': medication_management,
            'workflow_automation': workflow_automation,
            'predictive_insights': predictive_insights,
            'smart_recommendations': smart_recommendations,
            'quality_indicators': quality_indicators,
            'nursing_protocols': nursing_protocols,
            'workload_prediction': workload_prediction
        }
        
        return render_template(
            'nurse/dashboard_new.html',
            stats=stats,
            total_patients=total_patients,
            today_visits=today_visits,
            active_visits_list=active_visits_list,
            recent_visits=recent_visits,
            open_tasks=open_tasks,
            task_items=task_items[:20],
            safety_alerts=safety_alerts,
        )
    except Exception as e:
        logging.error(f"Error in nurse dashboard: {str(e)}")
        flash('حدث خطأ في تحميل لوحة التحكم', 'error')
        return redirect(url_for('main.dashboard'))

@nurse_bp.route('/api/protocols', methods=['GET', 'POST'])
@login_required
@role_required('nurse', 'admin', 'manager')
def api_nursing_protocols():
    if request.method == 'GET':
        return jsonify({'success': True, 'items': _get_nursing_protocols()}), 200
    data = request.get_json() or {}
    items = data.get('items') or []
    normalized = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = (item.get('title') or '').strip()
        if not title:
            continue
        steps = item.get('steps') or []
        if isinstance(steps, str):
            steps = [s.strip() for s in steps.split(',') if s.strip()]
        normalized.append({
            'id': item.get('id') or f"p_{len(normalized) + 1}",
            'title': title,
            'steps': steps
        })
    if not normalized:
        normalized = _default_nursing_protocols()
    _save_nursing_protocols(normalized)
    return jsonify({'success': True, 'items': normalized}), 200

# ==================== الميزات الذكية للتمريض ====================

def get_nursing_smart_analytics():
    """التحليلات الذكية للتمريض"""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import func
        from models.nurse import Nurse
        from models.task_management import Task

        # تحليل الممرضات
        total_nurses = Nurse.query.filter(Nurse.is_active == True).count()
        total_tasks = Task.query.filter(Task.task_type == 'nursing').count()
        completed_tasks = Task.query.filter(Task.task_type == 'nursing', Task.status == 'completed').count()
        pending_tasks = Task.query.filter(Task.task_type == 'nursing', Task.status == 'pending').count()
        
        # تحليل المهام
        urgent_tasks = Task.query.filter(Task.task_type == 'nursing', Task.priority == 'urgent').count()
        high_priority_tasks = Task.query.filter(Task.task_type == 'nursing', Task.priority == 'high').count()
        
        # تحليل الأداء
        completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        
        # تحليل أنواع المهام
        task_types = db.session.query(
        Task.task_type,
        func.count(Task.id).label('count')
    ).filter(Task.task_type == 'nursing').group_by(Task.task_type).all()

        return {
            'total_nurses': total_nurses,
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'pending_tasks': pending_tasks,
            'urgent_tasks': urgent_tasks,
            'high_priority_tasks': high_priority_tasks,
            'completion_rate': round(completion_rate, 2),
            'task_types': [{'type': t.task_type, 'count': t.count} for t in task_types],
            'efficiency_score': calculate_nursing_efficiency(completion_rate, pending_tasks, total_tasks)
        }
    except Exception as e:
        logging.error(f"Error getting nursing smart analytics: {str(e)}")
        return {}

def get_patient_care_optimization():
    """تحسين رعاية المرضى"""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import func
        from models.task_management import Task

        # تحليل المهام
        total_tasks = Task.query.filter(Task.task_type == 'nursing').count()
        completed_tasks = Task.query.filter(Task.task_type == 'nursing', Task.status == 'completed').count()
        in_progress_tasks = Task.query.filter(Task.task_type == 'nursing', Task.status == 'in_progress').count()
        
        # تحليل الأولويات
        urgent_tasks = Task.query.filter(Task.task_type == 'nursing', Task.priority == 'urgent').count()
        high_priority_tasks = Task.query.filter(Task.task_type == 'nursing', Task.priority == 'high').count()
        
        # تحليل أوقات الإنجاز
        avg_completion_time = 0  # يمكن حساب متوسط وقت الإنجاز
        
        # اقتراحات التحسين
        optimization_suggestions = generate_patient_care_optimization_suggestions(
            urgent_tasks, high_priority_tasks, total_tasks
        )

        return {
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'in_progress_tasks': in_progress_tasks,
            'urgent_tasks': urgent_tasks,
            'high_priority_tasks': high_priority_tasks,
            'avg_completion_time': avg_completion_time,
            'optimization_suggestions': optimization_suggestions,
            'efficiency_score': calculate_patient_care_efficiency(completed_tasks, total_tasks)
        }
    except Exception as e:
        logging.error(f"Error getting patient care optimization: {str(e)}")
        return {}

def get_vital_signs_monitoring():
    """مراقبة العلامات الحيوية"""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import func
        from models.nurse import VitalSigns

        # تحليل العلامات الحيوية
        total_vital_signs = VitalSigns.query.count()
        abnormal_vital_signs = VitalSigns.query.filter(
            or_(
                VitalSigns.blood_pressure_systolic > 140,
                VitalSigns.blood_pressure_diastolic > 90,
                VitalSigns.heart_rate > 100,
                VitalSigns.temperature > 37.5
            )
        ).count()
        
        # تحليل الاتجاهات
        recent_vital_signs = VitalSigns.query.filter(
            VitalSigns.recorded_at >= datetime.now() - timedelta(days=7)
        ).count()
        
        # تحليل التنبيهات
        critical_alerts = VitalSigns.query.filter(
            or_(
                VitalSigns.blood_pressure_systolic > 160,
                VitalSigns.heart_rate > 120,
                VitalSigns.temperature > 38.5
            )
        ).count()

        return {
            'total_vital_signs': total_vital_signs,
            'abnormal_vital_signs': abnormal_vital_signs,
            'recent_vital_signs': recent_vital_signs,
            'critical_alerts': critical_alerts,
            'monitoring_score': calculate_vital_signs_monitoring_score(abnormal_vital_signs, critical_alerts, total_vital_signs)
        }
    except Exception as e:
        logging.error(f"Error getting vital signs monitoring: {str(e)}")
        return {}

def get_medication_management():
    """إدارة الأدوية"""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import func
        from models.task_management import Task
        from models.medication import Medication

        # تحليل إعطاء الأدوية
        medication_tasks = Task.query.filter(Task.task_type == 'nursing').count()
        completed_medication_tasks = Task.query.filter(
            and_(
                Task.task_type == 'nursing',
                Task.status == 'completed'
            )
        ).count()
        
        # تحليل الأدوية المطلوبة
        medications_needed = Medication.query.filter(
            Medication.stock_quantity <= Medication.minimum_stock
        ).count()
        
        # تحليل الأخطاء
        medication_errors = 0  # يمكن إضافة نموذج للأخطاء
        
        # تحليل التوقيت
        on_time_medications = 0  # يمكن حساب الأدوية في الوقت المحدد

        return {
            'medication_tasks': medication_tasks,
            'completed_medication_tasks': completed_medication_tasks,
            'medications_needed': medications_needed,
            'medication_errors': medication_errors,
            'on_time_medications': on_time_medications,
            'medication_efficiency': calculate_medication_efficiency(completed_medication_tasks, medication_tasks)
        }
    except Exception as e:
        logging.error(f"Error getting medication management: {str(e)}")
        return {}

def get_nursing_workflow_automation():
    """أتمتة سير عمل التمريض"""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import func
        from models.task_management import Task

        # تحليل المهام المؤتمتة
        automated_tasks = 0  # يمكن إضافة نموذج للمهام المؤتمتة
        manual_tasks = Task.query.filter(Task.task_type == 'nursing').count()
        
        # تحليل أوقات المعالجة
        avg_processing_time = 0  # يمكن حساب متوسط وقت المعالجة
        
        # تحليل الكفاءة
        efficiency_metrics = {
            'automation_rate': 0,
            'time_saved': 0,
            'error_reduction': 0,
            'productivity_gain': 0
        }

        return {
            'automated_tasks': automated_tasks,
            'manual_tasks': manual_tasks,
            'avg_processing_time': avg_processing_time,
            'efficiency_metrics': efficiency_metrics,
            'automation_score': calculate_nursing_automation_score(automated_tasks, manual_tasks)
        }
    except Exception as e:
        logging.error(f"Error getting nursing workflow automation: {str(e)}")
        return {}

def get_nursing_predictive_insights():
    try:
        from datetime import datetime, timedelta
        from models.task_management import Task
        from models.nurse import VitalSigns
        from models.visit import Visit

        now = datetime.now(timezone.utc)
        weekly_tasks = Task.query.filter(
            Task.task_type == 'nursing',
            Task.created_at >= now - timedelta(days=7)
        ).count()
        monthly_tasks = Task.query.filter(
            Task.task_type == 'nursing',
            Task.created_at >= now - timedelta(days=30)
        ).count()
        prev_week = Task.query.filter(
            Task.task_type == 'nursing',
            Task.created_at >= now - timedelta(days=14),
            Task.created_at < now - timedelta(days=7)
        ).count()
        growth_rate = ((weekly_tasks - prev_week) / prev_week * 100) if prev_week else 0

        active_visits = Visit.query.filter(Visit.status.in_(['OPEN', 'IN_PROGRESS'])).count()
        recent_vitals = VitalSigns.query.filter(VitalSigns.recorded_at >= now - timedelta(hours=6)).count()
        predicted_workload = int(active_visits + (recent_vitals / 10))

        return {
            'weekly_tasks': weekly_tasks,
            'monthly_tasks': monthly_tasks,
            'growth_rate': round(growth_rate, 2),
            'peak_hours': [],
            'predicted_workload': predicted_workload,
            'workload_forecast_accuracy': calculate_workload_forecast_accuracy()
        }
    except Exception as e:
        logging.error(f"Error getting nursing predictive insights: {str(e)}")
        return {}

def get_nursing_quality_indicators():
    try:
        from models.nurse import VitalSigns, MedicationAdministrationLog
        from models.task_management import Task
        now = datetime.now(timezone.utc)
        last_7 = now - timedelta(days=7)
        vitals_critical = VitalSigns.query.filter(
            VitalSigns.recorded_at >= last_7,
            VitalSigns.oxygen_saturation.isnot(None),
            VitalSigns.oxygen_saturation < 90
        ).count()
        overdue_tasks = Task.query.filter(
            Task.task_type == 'nursing',
            Task.due_date.isnot(None),
            Task.due_date < now,
            Task.status.in_(['pending', 'in_progress', 'on_hold'])
        ).count()
        med_logs = MedicationAdministrationLog.query.filter(
            MedicationAdministrationLog.administered_at >= last_7
        ).count()
        documentation_rate = 100 if med_logs else 80
        return {
            'critical_vitals_7d': int(vitals_critical or 0),
            'overdue_tasks': int(overdue_tasks or 0),
            'documentation_rate': int(documentation_rate),
            'safety_score': max(0, 100 - (int(vitals_critical or 0) * 2) - (int(overdue_tasks or 0)))
        }
    except Exception:
        return {}

def get_nursing_workload_prediction():
    try:
        from models.visit import Visit
        from models.task_management import Task
        active_visits = Visit.query.filter(Visit.status.in_(['OPEN', 'IN_PROGRESS'])).count()
        pending_tasks = Task.query.filter(Task.task_type == 'nursing', Task.status.in_(['pending', 'in_progress'])).count()
        predicted = int(active_visits + (pending_tasks / 2))
        return {
            'active_visits': int(active_visits or 0),
            'pending_tasks': int(pending_tasks or 0),
            'predicted_load': predicted
        }
    except Exception:
        return {}

def get_nursing_smart_recommendations():
    """التوصيات الذكية للتمريض"""
    try:
        recommendations = []
        
        # تحليل البيانات الحالية
        analytics = get_nursing_smart_analytics()
        patient_care = get_patient_care_optimization()
        vital_signs = get_vital_signs_monitoring()
        medication = get_medication_management()
        workflow = get_nursing_workflow_automation()

        # توصيات بناءً على التحليل
        if analytics.get('urgent_tasks', 0) > 3:
            recommendations.append({
                'title': 'تسريع المهام العاجلة',
                'description': f'عدد المهام العاجلة {analytics.get("urgent_tasks", 0)} مرتفع. يُنصح بتسريع المعالجة.',
                'priority': 'high',
                'category': 'urgent_tasks'
            })

        if patient_care.get('completion_rate', 0) < 80:
            recommendations.append({
                'title': 'تحسين معدل إنجاز المهام',
                'description': f'معدل إنجاز المهام {patient_care.get("completion_rate", 0)}% منخفض. يُنصح بتحسين الكفاءة.',
                'priority': 'medium',
                'category': 'efficiency'
            })

        if vital_signs.get('critical_alerts', 0) > 0:
            recommendations.append({
                'title': 'متابعة العلامات الحيوية الحرجة',
                'description': f'يوجد {vital_signs.get("critical_alerts", 0)} تنبيه حرج للعلامات الحيوية. يُنصح بالمتابعة الفورية.',
                'priority': 'high',
                'category': 'vital_signs'
            })

        if medication.get('medication_errors', 0) > 0:
            recommendations.append({
                'title': 'تقليل أخطاء الأدوية',
                'description': f'يوجد {medication.get("medication_errors", 0)} خطأ في الأدوية. يُنصح بتحسين الدقة.',
                'priority': 'high',
                'category': 'medication_safety'
            })

        if workflow.get('automation_score', 0) < 30:
            recommendations.append({
                'title': 'زيادة أتمتة المهام',
                'description': f'درجة الأتمتة {workflow.get("automation_score", 0)}% منخفضة. يُنصح بزيادة الأتمتة.',
                'priority': 'medium',
                'category': 'automation'
            })

        return {
            'recommendations': recommendations,
            'total_recommendations': len(recommendations),
            'high_priority': len([r for r in recommendations if r['priority'] == 'high']),
            'medium_priority': len([r for r in recommendations if r['priority'] == 'medium'])
        }
    except Exception as e:
        logging.error(f"Error getting nursing smart recommendations: {str(e)}")
        return {'recommendations': [], 'total_recommendations': 0}

# ==================== دوال مساعدة ====================

def calculate_nursing_efficiency(completion_rate, pending_tasks, total_tasks):
    """حساب كفاءة التمريض"""
    try:
        if total_tasks == 0:
            return 0
        
        efficiency = (completion_rate * 0.7) + ((total_tasks - pending_tasks) / total_tasks * 0.3)
        return min(100, max(0, round(efficiency, 2)))
    except:
        return 0

def generate_patient_care_optimization_suggestions(urgent_tasks, high_priority_tasks, total_tasks):
    """توليد اقتراحات تحسين رعاية المرضى"""
    suggestions = []
    
    try:
        if urgent_tasks > total_tasks * 0.1:
            suggestions.append('زيادة عدد الممرضات للمهام العاجلة')
        
        if high_priority_tasks > total_tasks * 0.3:
            suggestions.append('تحسين توزيع الأولويات')
        
        if not suggestions:
            suggestions.append('رعاية المرضى في حالة جيدة')
            
    except Exception as e:
        suggestions.append('تحليل البيانات للتحسين')
    
    return suggestions

def calculate_patient_care_efficiency(completed_tasks, total_tasks):
    """حساب كفاءة رعاية المرضى"""
    try:
        if total_tasks == 0:
            return 0
        
        efficiency = (completed_tasks / total_tasks) * 100
        return min(100, max(0, round(efficiency, 2)))
    except:
        return 0

def calculate_vital_signs_monitoring_score(abnormal_vital_signs, critical_alerts, total_vital_signs):
    """حساب درجة مراقبة العلامات الحيوية"""
    try:
        if total_vital_signs == 0:
            return 100
        
        monitoring_score = 100
        monitoring_score -= (abnormal_vital_signs / total_vital_signs) * 20
        monitoring_score -= (critical_alerts / total_vital_signs) * 30
        
        return min(100, max(0, round(monitoring_score, 2)))
    except:
        return 0

def calculate_medication_efficiency(completed_medication_tasks, medication_tasks):
    """حساب كفاءة إدارة الأدوية"""
    try:
        if medication_tasks == 0:
            return 0
        
        efficiency = (completed_medication_tasks / medication_tasks) * 100
        return min(100, max(0, round(efficiency, 2)))
    except:
        return 0

def calculate_nursing_automation_score(automated_tasks, manual_tasks):
    """حساب درجة أتمتة التمريض"""
    try:
        if automated_tasks + manual_tasks == 0:
            return 0
        
        automation_rate = (automated_tasks / (automated_tasks + manual_tasks)) * 100
        return min(100, max(0, round(automation_rate, 2)))
    except:
        return 0

def calculate_workload_forecast_accuracy():
    """حساب دقة التنبؤ بالحمل"""
    try:
        # يمكن تطوير خوارزمية أكثر تعقيداً هنا
        return 85  # قيمة افتراضية
    except:
        return 0

@nurse_bp.route('/patient-care')
@login_required
def patient_care():
    """رعاية المرضى"""
    if current_user.role not in ['nurse', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        patients = Patient.query.order_by(desc(Patient.created_at)).limit(20).all()
        
        return render_template('nurse/patient_care.html', patients=patients)
    except Exception as e:
        logging.error(f"Error loading patient care: {str(e)}")
        flash('حدث خطأ في تحميل رعاية المرضى', 'error')
        return redirect(url_for('nurse.dashboard'))

@nurse_bp.route('/medication-administration')
@login_required
@role_required('nurse', 'admin', 'manager')
def medication_administration():
    """إدارة الأدوية"""
    
    
    try:
        from models.medication import Prescription, PrescriptionItem
        from models.nurse import MedicationAdministrationLog

        visit_id = request.args.get('visit_id', type=int)

        medications = Medication.query.filter_by(is_active=True).order_by(Medication.trade_name.asc()).all()
        needed_medications = Medication.query.filter(
            Medication.stock_quantity <= Medication.minimum_stock
        ).order_by(Medication.trade_name.asc()).all()

        visits_q = Visit.query.filter(Visit.status.in_(['OPEN', 'IN_PROGRESS']))
        dept_ids = _accessible_department_ids()
        if dept_ids is not None and dept_ids:
            visits_q = visits_q.filter(Visit.department_id.in_(dept_ids))
        visits = visits_q.order_by(desc(Visit.created_at)).limit(50).all()
        selected_visit = db.session.get(Visit, visit_id) if visit_id else None

        prescribed_items = []
        administration_logs = []
        last_admin_by_item = {}
        if selected_visit:
            prescribed_items = PrescriptionItem.query.join(
                Prescription, PrescriptionItem.prescription_id == Prescription.id
            ).filter(
                Prescription.visit_id == selected_visit.id
            ).order_by(PrescriptionItem.id.desc()).all()

            administration_logs = MedicationAdministrationLog.query.filter_by(
                visit_id=selected_visit.id
            ).order_by(desc(MedicationAdministrationLog.administered_at)).limit(50).all()

            for row in administration_logs:
                if row.prescription_item_id and row.prescription_item_id not in last_admin_by_item:
                    last_admin_by_item[row.prescription_item_id] = row

        return render_template(
            'nurse/medication_administration.html',
            medications=medications,
            needed_medications=needed_medications,
            visits=visits,
            selected_visit=selected_visit,
            prescribed_items=prescribed_items,
            administration_logs=administration_logs,
            last_admin_by_item=last_admin_by_item
        )
    except Exception as e:
        logging.error(f"Error loading medication administration: {str(e)}")
        flash('حدث خطأ في تحميل إدارة الأدوية', 'error')
        return redirect(url_for('nurse.dashboard'))


@nurse_bp.route('/administer-medication/<int:prescription_item_id>', methods=['POST'])
@login_required
@role_required('nurse', 'admin', 'manager')
def administer_medication(prescription_item_id):
    try:
        from models.medication import Prescription, PrescriptionItem
        from models.nurse import MedicationAdministrationLog

        nurse_profile = getattr(current_user, 'nurse_profile', None)
        if isinstance(nurse_profile, (list, tuple)):
            nurse_profile = nurse_profile[0] if nurse_profile else None
        if not nurse_profile:
            flash('لا يوجد ملف تمريض مرتبط بهذا المستخدم', 'error')
            return redirect(url_for('nurse.medication_administration'))

        item = db.session.get(PrescriptionItem, prescription_item_id)
        if not item:
            flash('عنصر الوصفة غير موجود', 'error')
            return redirect(url_for('nurse.medication_administration'))

        pres = db.session.get(Prescription, item.prescription_id)
        if not pres or not pres.visit_id:
            flash('لا يمكن ربط عنصر الوصفة بزيارة', 'error')
            return redirect(url_for('nurse.medication_administration'))

        visit = db.session.get(Visit, pres.visit_id)
        if not visit:
            flash('الزيارة غير موجودة', 'error')
            return redirect(url_for('nurse.medication_administration'))

        notes = (request.form.get('notes') or '').strip() or None
        log_row = MedicationAdministrationLog(
            patient_id=pres.patient_id or visit.patient_id,
            visit_id=visit.id,
            prescription_id=pres.id,
            prescription_item_id=item.id,
            medication_id=item.medication_id,
            nurse_id=nurse_profile.id,
            administered_at=datetime.now(timezone.utc),
            notes=notes
        )
        db.session.add(log_row)
        db.session.commit()
        flash('تم توثيق تنفيذ الدواء', 'success')
        return redirect(url_for('nurse.medication_administration', visit_id=visit.id))
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error administering medication: {str(e)}")
        flash('حدث خطأ في توثيق تنفيذ الدواء', 'error')
        return redirect(url_for('nurse.medication_administration'))

@nurse_bp.route('/patient-monitoring')
@login_required
def patient_monitoring():
    """مراقبة المرضى"""
    if current_user.role not in ['nurse', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        patients = Patient.query.order_by(desc(Patient.created_at)).limit(20).all()
        
        return render_template('nurse/patient_monitoring.html', patients=patients)
    except Exception as e:
        logging.error(f"Error loading patient monitoring: {str(e)}")
        flash('حدث خطأ في تحميل مراقبة المرضى', 'error')
        return redirect(url_for('nurse.dashboard'))

@nurse_bp.route('/vital-signs')
@login_required
def vital_signs():
    """العلامات الحيوية"""
    if current_user.role not in ['nurse', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        from models.nurse import VitalSigns

        visit_id = request.args.get('visit_id', type=int)
        patient_id = request.args.get('patient_id', type=int)
        if not patient_id and visit_id:
            visit = db.session.get(Visit, visit_id)
            if visit:
                patient_id = visit.patient_id
        vq = Visit.query.filter(Visit.status.in_(['OPEN', 'IN_PROGRESS']))
        dept_ids = _accessible_department_ids()
        if dept_ids is not None and dept_ids:
            vq = vq.filter(Visit.department_id.in_(dept_ids))
            vq = vq.filter(Visit.department_id.in_(dept_ids))
        active_patient_ids = [r.patient_id for r in vq.order_by(desc(Visit.created_at)).limit(50).all() if getattr(r, 'patient_id', None)]
        patients = []
        if active_patient_ids:
            patients = Patient.query.filter(Patient.id.in_(active_patient_ids)).order_by(desc(Patient.created_at)).all()
        else:
            patients = Patient.query.order_by(desc(Patient.created_at)).limit(20).all()

        selected_patient = db.session.get(Patient, patient_id) if patient_id else None
        vital_records = []
        if selected_patient:
            vital_records = VitalSigns.query.filter_by(patient_id=selected_patient.id).order_by(
                desc(VitalSigns.recorded_at)
            ).limit(20).all()
        
        return render_template(
            'nurse/vital_signs.html',
            patients=patients,
            selected_patient=selected_patient,
            vital_records=vital_records
        )
    except Exception as e:
        logging.error(f"Error loading vital signs: {str(e)}")
        flash('حدث خطأ في تحميل العلامات الحيوية', 'error')
        return redirect(url_for('nurse.dashboard'))

@nurse_bp.route('/record-vital-signs/<int:patient_id>', methods=['POST'])
@login_required
def record_vital_signs(patient_id):
    """تسجيل العلامات الحيوية"""
    if current_user.role not in ['nurse', 'admin', 'manager']:
        return jsonify({'success': False, 'message': 'غير مصرح'}), 403
    
    try:
        from models.nurse import VitalSigns

        patient = db.session.get(Patient, patient_id)
        if not patient:
            return jsonify({'success': False, 'message': 'المريض غير موجود'}), 404

        nurse_profile = getattr(current_user, 'nurse_profile', None)
        if isinstance(nurse_profile, (list, tuple)):
            nurse_profile = nurse_profile[0] if nurse_profile else None
        nurse_profile = nurse_profile if nurse_profile else None
        if not nurse_profile:
            return jsonify({'success': False, 'message': 'لا يوجد ملف تمريض مرتبط بهذا المستخدم'}), 400

        bp_systolic_raw = request.form.get('blood_pressure_systolic')
        bp_diastolic_raw = request.form.get('blood_pressure_diastolic')
        bp_raw = (request.form.get('blood_pressure') or '').strip()
        if (not bp_systolic_raw and not bp_diastolic_raw) and bp_raw and '/' in bp_raw:
            parts = [p.strip() for p in bp_raw.split('/') if p.strip()]
            if len(parts) >= 2:
                bp_systolic_raw, bp_diastolic_raw = parts[0], parts[1]

        def _to_int(val):
            val = (val or '').strip()
            return int(val) if val else None

        def _to_float(val):
            val = (val or '').strip()
            return float(val) if val else None

        record = VitalSigns(
            patient_id=patient.id,
            nurse_id=nurse_profile.id,
            blood_pressure_systolic=_to_int(bp_systolic_raw),
            blood_pressure_diastolic=_to_int(bp_diastolic_raw),
            heart_rate=_to_int(request.form.get('heart_rate')),
            temperature=_to_float(request.form.get('temperature')),
            oxygen_saturation=_to_int(request.form.get('oxygen_saturation')),
            respiratory_rate=_to_int(request.form.get('respiratory_rate')),
            weight=_to_float(request.form.get('weight')),
            height=_to_float(request.form.get('height')),
            notes=(request.form.get('notes') or '').strip() or None
        )
        db.session.add(record)
        db.session.commit()

        return jsonify({'success': True, 'message': 'تم تسجيل العلامات الحيوية بنجاح', 'data': record.to_dict()})
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error recording vital signs: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر تسجيل العلامات الحيوية حالياً'})

@nurse_bp.route('/patients')
@login_required
def patients():
    """مرضى التمريض"""
    if current_user.role not in ['nurse', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    return redirect(url_for('nurse.patient_care'))

@nurse_bp.route('/vitals')
@login_required
@role_required('nurse', 'admin', 'manager')
def vitals():
    """العلامات الحيوية"""
    
    
    return redirect(url_for('nurse.vital_signs'))

@nurse_bp.route('/medications')
@login_required
@role_required('nurse', 'admin', 'manager')
def medications():
    """الأدوية"""
    
    
    return render_template('nurse/medication_administration.html')

@nurse_bp.route('/wards')
@login_required
def wards():
    """الأجنحة"""
    if current_user.role not in ['nurse', 'admin', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    return render_template('nurse/patient_monitoring.html')

@nurse_bp.route('/tasks')
@login_required
@role_required('nurse', 'admin', 'manager')
def tasks():
    """مهام التمريض"""
    page = request.args.get('page', 1, type=int)
    per_page = 25
    
    try:
        from models.task_management import Task
        vq = Visit.query.filter(Visit.status.in_(['OPEN', 'IN_PROGRESS'])).order_by(desc(Visit.created_at))
        if getattr(current_user, 'department_id', None):
            vq = vq.filter(Visit.department_id == current_user.department_id)
        active_visits = vq.limit(50).all()
        
        # جلب مهام الممرضة مع pagination
        task_query = Task.query.filter_by(assigned_to=current_user.id).order_by(Task.created_at.desc())
        
        total = task_query.count()
        pages = (total + per_page - 1) // per_page
        
        tasks = task_query.offset((page - 1) * per_page).limit(per_page).all()
        
    except Exception as e:
        logging.error(f"Error loading nurse tasks: {str(e)}")
        tasks = []
        total = 0
        pages = 0

    return render_template('nurse/tasks.html', tasks=tasks, active_visits=active_visits, now=datetime.now(timezone.utc),
                           page=page, pages=pages, total=total)
    except Exception as e:
        logging.error(f"Error loading nurse tasks: {str(e)}")
        flash('حدث خطأ في تحميل المهام', 'error')
        return redirect(url_for('nurse.dashboard'))


@nurse_bp.route('/tasks/create', methods=['POST'])
@login_required
@role_required('nurse', 'admin', 'manager')
def create_task():
    try:
        from models.task_management import Task

        title = (request.form.get('title') or '').strip()
        description = (request.form.get('description') or '').strip() or None
        priority = (request.form.get('priority') or 'medium').strip().lower()
        due_raw = (request.form.get('due_date') or '').strip()
        visit_id = request.form.get('visit_id', type=int)

        if not title:
            flash('يرجى إدخال عنوان المهمة', 'warning')
            return redirect(url_for('nurse.tasks'))
        if priority not in {'low', 'medium', 'high', 'urgent'}:
            priority = 'medium'

        due_date = None
        if due_raw:
            try:
                due_date = datetime.strptime(due_raw, '%Y-%m-%dT%H:%M')
                due_date = due_date.replace(tzinfo=timezone.utc)
            except Exception:
                due_date = None

        related_entity_type = None
        related_entity_id = None
        if visit_id:
            v = db.session.get(Visit, visit_id)
            if v:
                related_entity_type = 'visit'
                related_entity_id = v.id

        db.session.add(Task(
            title=title,
            description=description,
            task_type='patient_care',
            status='pending',
            priority=priority,
            assigned_to=current_user.id,
            assigned_by=current_user.id,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
            due_date=due_date,
        ))
        db.session.commit()
        flash('تمت إضافة المهمة', 'success')
        return redirect(url_for('nurse.tasks'))
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error creating nurse task: {str(e)}")
        flash('حدث خطأ أثناء إنشاء المهمة', 'error')
        return redirect(url_for('nurse.tasks'))


@nurse_bp.route('/tasks/<int:task_id>/status', methods=['POST'])
@login_required
@role_required('nurse', 'admin', 'manager')
def update_task_status(task_id: int):
    try:
        from models.task_management import Task

        t = db.session.get(Task, task_id)
        if not t:
            flash('المهمة غير موجودة', 'error')
            return redirect(url_for('nurse.tasks'))
        if current_user.role == 'nurse' and t.assigned_to != current_user.id:
            flash('ليس لديك صلاحية لتعديل هذه المهمة', 'error')
            return redirect(url_for('nurse.tasks'))

        status_val = (request.form.get('status') or '').strip().lower()
        allowed = {'pending', 'in_progress', 'completed', 'cancelled', 'on_hold'}
        if status_val not in allowed:
            flash('حالة غير صالحة', 'error')
            return redirect(url_for('nurse.tasks'))

        t.status = status_val
        if status_val == 'completed':
            t.completed_at = datetime.now(timezone.utc)
        else:
            t.completed_at = None
        t.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        flash('تم تحديث الحالة', 'success')
        return redirect(url_for('nurse.tasks'))
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error updating task status: {str(e)}")
        flash('حدث خطأ أثناء التحديث', 'error')
        return redirect(url_for('nurse.tasks'))


@nurse_bp.route('/reports')
@login_required
@role_required('nurse', 'admin', 'manager')
def reports():
    try:
        from models.task_management import Task
        from models.user import User
        from models.department import Department

        start_raw = (request.args.get('start_date') or '').strip()
        end_raw = (request.args.get('end_date') or '').strip()
        try:
            start_date = datetime.strptime(start_raw, '%Y-%m-%d').date() if start_raw else (date.today() - timedelta(days=30))
        except Exception:
            start_date = date.today() - timedelta(days=30)
        try:
            end_date = datetime.strptime(end_raw, '%Y-%m-%d').date() if end_raw else date.today()
        except Exception:
            end_date = date.today()

        start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        end_dt = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)

        base_q = db.session.query(Task, User).join(User, User.id == Task.assigned_to).filter(
            User.role == 'nurse',
            Task.created_at >= start_dt,
            Task.created_at <= end_dt
        )

        total_tasks = base_q.with_entities(func.count(Task.id)).scalar() or 0
        completed_tasks = base_q.with_entities(func.count(Task.id)).filter(Task.status == 'completed').scalar() or 0
        overdue_tasks = base_q.with_entities(func.count(Task.id)).filter(Task.due_date.isnot(None), Task.due_date < now, Task.status.in_(['pending', 'in_progress', 'on_hold'])).scalar() or 0
        urgent_tasks = base_q.with_entities(func.count(Task.id)).filter(Task.priority == 'urgent').scalar() or 0

        by_status = db.session.query(Task.status, func.count(Task.id)).join(User, User.id == Task.assigned_to).filter(
            User.role == 'nurse',
            Task.created_at >= start_dt,
            Task.created_at <= end_dt
        ).group_by(Task.status).all()
        by_priority = db.session.query(Task.priority, func.count(Task.id)).join(User, User.id == Task.assigned_to).filter(
            User.role == 'nurse',
            Task.created_at >= start_dt,
            Task.created_at <= end_dt
        ).group_by(Task.priority).all()

        by_department = db.session.query(
            Department.name_ar,
            func.count(Task.id)
        ).join(
            User, User.id == Task.assigned_to
        ).outerjoin(
            Department, Department.id == User.department_id
        ).filter(
            User.role == 'nurse',
            Task.created_at >= start_dt,
            Task.created_at <= end_dt
        ).group_by(Department.name_ar).all()

        top_overdue = base_q.filter(
            Task.due_date.isnot(None),
            Task.due_date < now,
            Task.status.in_(['pending', 'in_progress', 'on_hold'])
        ).order_by(Task.due_date.asc()).limit(25).all()

        rows = []
        for t, u in top_overdue:
            rows.append({
                'title': t.title,
                'nurse_name': u.full_name if u else '',
                'priority': t.priority,
                'status': t.status,
                'due_date': t.due_date,
            })

        return render_template(
            'nurse/reports.html',
            start_date=start_date,
            end_date=end_date,
            total_tasks=int(total_tasks),
            completed_tasks=int(completed_tasks),
            overdue_tasks=int(overdue_tasks),
            urgent_tasks=int(urgent_tasks),
            by_status=by_status,
            by_priority=by_priority,
            by_department=by_department,
            overdue_rows=rows
        )
    except Exception as e:
        logging.error(f"Error loading nurse reports: {str(e)}")
        flash('حدث خطأ في تحميل تقرير التمريض', 'error')
        return redirect(url_for('nurse.dashboard'))
