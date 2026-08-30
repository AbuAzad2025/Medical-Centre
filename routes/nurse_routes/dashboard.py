"""dashboard routes - extracted from monolithic nurse_routes.py"""

import logging
from datetime import UTC, datetime, timedelta

# Imports
from flask import flash, redirect, url_for
from flask_login import current_user, login_required
from sqlalchemy import desc, func, select

from app.extensions import db
from app.shared.enums import PrescriptionState, TaskState
from models.medication import Medication
from models.patient import Patient
from models.visit import Visit
from routes.nurse_routes import (
    _accessible_department_ids,
    _get_nursing_protocols,
    get_medication_management,
    get_nursing_predictive_insights,
    get_nursing_quality_indicators,
    get_nursing_smart_analytics,
    get_nursing_smart_recommendations,
    get_nursing_workflow_automation,
    get_nursing_workload_prediction,
    get_patient_care_optimization,
    get_vital_signs_monitoring,
    nurse_bp,
)
from services.core_queries import core_queries
from utils.decorators import role_required

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
        from models.medication import Prescription, PrescriptionItem
        from models.nurse import MedicationAdministrationLog, VitalSigns
        from models.task_management import Task

        base = core_queries.get_basic_dashboard_stats()
        today = datetime.now(UTC).date()
        start_of_today = datetime.combine(today, datetime.min.time(), tzinfo=UTC)
        datetime.combine(today, datetime.max.time(), tzinfo=UTC)

        base['total_patients']
        db.session.execute(
            select(func.count()).select_from(Patient).filter(
                Patient.tenant_id == current_user.tenant_id if hasattr(Patient, 'tenant_id') and current_user.tenant_id else True,
                Patient.created_at >= start_of_today
            )
        ).scalar()

        active_visits_query = select(Visit)
        if current_user.tenant_id is not None and hasattr(Visit, 'tenant_id'):
            active_visits_query = active_visits_query.filter(Visit.tenant_id == current_user.tenant_id)
        dept_ids = _accessible_department_ids()
        if dept_ids is not None and dept_ids:
            active_visits_query = active_visits_query.filter(Visit.department_id.in_(dept_ids))

        (
            db.session.execute(
                select(func.count()).select_from(active_visits_query.subquery())
            ).scalar()
            or 0
        )
        active_visits_list = (
            db.session.execute(active_visits_query.order_by(desc(Visit.created_at)).limit(20))
            .scalars()
            .all()
        )

        db.session.execute(
            select(func.count()).select_from(Visit).filter(
                Visit.tenant_id == current_user.tenant_id if hasattr(Visit, 'tenant_id') and current_user.tenant_id else True,
                Visit.visit_date == today
            )
        ).scalar()
        (
            db.session.execute(select(Visit).filter(
                Visit.tenant_id == current_user.tenant_id if hasattr(Visit, 'tenant_id') and current_user.tenant_id else True
            ).order_by(desc(Visit.created_at)).limit(20))
            .scalars()
            .all()
        )

        # الأدوية المطلوبة
        db.session.execute(
            select(func.count())
            .select_from(Medication)
            .filter(Medication.stock_quantity <= Medication.minimum_stock)
        ).scalar()

        open_tasks = (
            db.session.execute(
                select(Task)
                .filter(
                    Task.assigned_to == current_user.id,
                    Task.status.in_([TaskState.PENDING, TaskState.IN_PROGRESS]),
                )
                .order_by(desc(Task.created_at))
                .limit(10)
            )
            .scalars()
            .all()
        )

        vital_due_count = 0
        meds_due_count = 0
        task_items = []

        active_visit_ids = [v.id for v in active_visits_list if getattr(v, 'id', None)]
        active_patient_ids = [
            v.patient_id for v in active_visits_list if getattr(v, 'patient_id', None)
        ]

        latest_vitals_by_patient = {}
        if active_patient_ids:
            rows = (
                db.session.execute(
                    select(VitalSigns)
                    .filter(VitalSigns.patient_id.in_(active_patient_ids))
                    .order_by(desc(VitalSigns.recorded_at))
                )
                .scalars()
                .all()
            )
            for r in rows:
                if r.patient_id not in latest_vitals_by_patient:
                    latest_vitals_by_patient[r.patient_id] = r

        last_admin_by_item = {}
        if active_visit_ids:
            logs = (
                db.session.execute(
                    select(MedicationAdministrationLog)
                    .filter(MedicationAdministrationLog.visit_id.in_(active_visit_ids))
                    .order_by(desc(MedicationAdministrationLog.administered_at))
                    .limit(300)
                )
                .scalars()
                .all()
            )
            for row in logs:
                if row.prescription_item_id and row.prescription_item_id not in last_admin_by_item:
                    last_admin_by_item[row.prescription_item_id] = row

        prescribed_items_by_visit = {}
        if active_visit_ids:
            prescribed = (
                db.session.execute(
                    select(PrescriptionItem)
                    .join(Prescription, PrescriptionItem.prescription_id == Prescription.id)
                    .filter(
                        Prescription.visit_id.in_(active_visit_ids),
                        Prescription.status == PrescriptionState.ACTIVE,
                    )
                )
                .scalars()
                .all()
            )
            for it in prescribed:
                visit_id = getattr(getattr(it, 'prescription', None), 'visit_id', None)
                if not visit_id:
                    continue
                prescribed_items_by_visit.setdefault(visit_id, []).append(it)

        now = datetime.now(UTC)
        vital_due_after = timedelta(hours=4)
        for v in active_visits_list:
            last_vs = latest_vitals_by_patient.get(v.patient_id)
            last_vs_dt = getattr(last_vs, 'recorded_at', None)
            if last_vs_dt and not last_vs_dt.tzinfo:
                last_vs_dt = last_vs_dt.replace(tzinfo=UTC)
            vs_due = (not last_vs_dt) or (now - last_vs_dt > vital_due_after)
            if vs_due:
                vital_due_count += 1
                task_items.append(
                    {
                        'type': 'vitals',
                        'title': 'قياس العلامات الحيوية',
                        'visit_id': v.id,
                        'patient_name': v.patient.full_name if getattr(v, 'patient', None) else '',
                        'url': url_for('nurse.vital_signs', visit_id=v.id),
                        'priority': 'high' if getattr(v, 'is_emergency', False) else 'medium',
                    }
                )

            items = prescribed_items_by_visit.get(v.id) or []
            unadmin = [it for it in items if it.id not in last_admin_by_item]
            if unadmin:
                meds_due_count += 1
                task_items.append(
                    {
                        'type': 'meds',
                        'title': 'تنفيذ أدوية موصوفة',
                        'visit_id': v.id,
                        'patient_name': v.patient.full_name if getattr(v, 'patient', None) else '',
                        'url': url_for('nurse.medication_administration', visit_id=v.id),
                        'priority': 'medium',
                    }
                )

        int(len(open_tasks) + vital_due_count + meds_due_count)

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
                patient_name_by_id[v.patient_id] = (
                    v.patient.full_name if getattr(v, 'patient', None) else ''
                )

        vitals_alerts = []
        for pid, vs in (latest_vitals_by_patient or {}).items():
            if not vs:
                continue
            abnormal, critical = _vitals_flags(vs)
            if not abnormal and not critical:
                continue
            recorded_at = getattr(vs, 'recorded_at', None)
            if recorded_at and not recorded_at.tzinfo:
                recorded_at = recorded_at.replace(tzinfo=UTC)
            if not recorded_at:
                continue
            age_minutes = (now - recorded_at).total_seconds() / 60.0
            if critical and age_minutes >= 15:
                vitals_alerts.append(
                    {
                        'severity': 'critical',
                        'patient_id': pid,
                        'patient_name': patient_name_by_id.get(pid) or f'#{pid}',
                        'recorded_at': recorded_at,
                        'url': url_for('nurse.vital_signs', patient_id=pid),
                    }
                )
            elif abnormal and age_minutes >= 60:
                vitals_alerts.append(
                    {
                        'severity': 'abnormal',
                        'patient_id': pid,
                        'patient_name': patient_name_by_id.get(pid) or f'#{pid}',
                        'recorded_at': recorded_at,
                        'url': url_for('nurse.vital_signs', patient_id=pid),
                    }
                )

        overdue_tasks_q = select(Task)
        overdue_tasks_count = (
            db.session.execute(
                select(func.count()).select_from(overdue_tasks_q.subquery())
            ).scalar()
            or 0
        )
        overdue_important = (
            db.session.execute(
                overdue_tasks_q.filter(Task.priority.in_(['high', 'urgent']))
                .order_by(Task.due_date.asc())
                .limit(10)
            )
            .scalars()
            .all()
        )
        overdue_any = (
            db.session.execute(overdue_tasks_q.order_by(Task.due_date.asc()).limit(10))
            .scalars()
            .all()
        )

        {
            'vitals_alerts': vitals_alerts[:10],
            'vitals_alerts_count': len(vitals_alerts),
            'overdue_tasks_count': int(overdue_tasks_count or 0),
            'overdue_important': overdue_important,
            'overdue_any': overdue_any,
        }

        # الميزات الذكية
        get_nursing_smart_analytics()
        get_patient_care_optimization()
        get_vital_signs_monitoring()
        get_medication_management()
        get_nursing_workflow_automation()
        get_nursing_predictive_insights()
        get_nursing_smart_recommendations()
        get_nursing_quality_indicators()
        _get_nursing_protocols()
        get_nursing_workload_prediction()

        from app.shared.dashboard_service import render_command_center

        return render_command_center(current_user)
    except Exception:
        logging.exception('Error in nurse dashboard: %s')
        flash('حدث خطأ في تحميل لوحة التحكم', 'error')
        return redirect(url_for('main.dashboard'))
