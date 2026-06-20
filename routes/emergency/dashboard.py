"""dashboard routes - extracted from monolithic emergency.py"""

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
from services.core_queries import core_queries
from sqlalchemy import and_, or_, desc, case
import logging, json
from datetime import datetime, date, timedelta, timezone


# =============================================
# DASHBOARD ROUTES
# =============================================

@emergency_bp.route('/')
@login_required
def index():
    return redirect(url_for('emergency.dashboard'))

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

                logging.warning(f"Error in {__name__}: {e}")
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
