"""dashboard routes - extracted from monolithic nurse_routes.py"""

from routes.nurse_routes import nurse_bp

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from utils.decorators import role_required
from models.patient import Patient
from models.visit import Visit
from models.medication import Medication
from services.nursing_service import nursing_service
from app_factory import db
from services.core_queries import core_queries
import logging, json
from datetime import datetime, timedelta, timezone, date
from sqlalchemy import func, and_, or_, desc


# =============================================
# DASHBOARD ROUTES
# =============================================

@nurse_bp.route('/')
@login_required
def index():
    return redirect(url_for('nurse.dashboard'))

@nurse_bp.route('/dashboard')
@login_required
@role_required('nurse', 'admin', 'manager')
def dashboard():
    """لوحة تحكم الممرضة"""
    
    try:
        from models.task_management import Task
        from models.nurse import VitalSigns, MedicationAdministrationLog
        from models.medication import Prescription, PrescriptionItem

        base = core_queries.get_basic_dashboard_stats()
        today = datetime.now(timezone.utc).date()
        start_of_today = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc)
        end_of_today = datetime.combine(today, datetime.max.time(), tzinfo=timezone.utc)

        total_patients = base["total_patients"]
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
