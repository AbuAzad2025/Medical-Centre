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

from services.feature_gate_service import guard_module

@emergency_bp.before_request
def _guard_emergency_module():
    guard_module('emergency')


def _normalize_emergency_status(value):
    v = (value or '').strip().upper()
    if not v:
        return None
    alias = {
        'ACTIVE': 'WAITING',
        'RESOLVED': 'COMPLETED',
    }
    v = alias.get(v, v)
    allowed = {
        'WAITING',
        'TRIAGE',
        'RESUSCITATION',
        'TREATMENT',
        'OBSERVATION',
        'IN_PROGRESS',
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



























def get_emergency_time_metrics():
    try:
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=7)
        rows = EmergencyCase.query.filter(EmergencyCase.created_at >= start).all()
        if not rows:
            return {'avg_triage_time': 0, 'avg_treatment_time': 0, 'avg_disposition_time': 0, 'door_to_disposition_rate': 0, 'triage_sla_compliance': 0}
        triage_times = []
        treatment_times = []
        los_times = []
        triage_within_sla = 0
        total_triaged = 0
        for c in rows:
            created = c.created_at
            if not created:
                continue
            updated = c.updated_at or created
            if c.status in ['TRIAGE', 'RESUSCITATION', 'TREATMENT', 'OBSERVATION', 'COMPLETED']:
                triage_min = (updated - created).total_seconds() / 60
                triage_times.append(triage_min)
                total_triaged += 1
                if triage_min <= 10:
                    triage_within_sla += 1
            if c.status in ['TREATMENT', 'OBSERVATION', 'COMPLETED']:
                treatment_times.append((updated - created).total_seconds() / 60)
            if c.completed_at:
                los_times.append((c.completed_at - created).total_seconds() / 60)
        def _avg(vals):
            return round(sum(vals) / len(vals), 2) if vals else 0
        avg_los = _avg(los_times)
        return {
            'avg_triage_time': _avg(triage_times),
            'avg_treatment_time': _avg(treatment_times),
            'avg_disposition_time': avg_los,
            'door_to_disposition_rate': round((len(los_times) / max(len(rows), 1)) * 100, 1),
            'triage_sla_compliance': round((triage_within_sla / max(total_triaged, 1)) * 100, 1)
        }
    except Exception:
        return {}

def get_emergency_protocols():
    try:
        protocols = [
            {'id': 'stroke', 'name': 'بروتوكول السكتة الدماغية', 'title': 'بروتوكول السكتة الدماغية', 'keywords': ['ضعف', 'شلل', 'سكتة', 'stroke'], 'steps': ['تقييم FAST', 'CT عاجل', 'تفعيل فريق السكتة']},
            {'id': 'mi', 'name': 'بروتوكول MI', 'title': 'بروتوكول MI', 'keywords': ['صدر', 'ألم صدري', 'mi', 'heart'], 'steps': ['ECG خلال 10 دقائق', 'مخبر قلب', 'تحضير قسطرة']},
            {'id': 'trauma', 'name': 'بروتوكول الإصابات', 'title': 'بروتوكول الإصابات', 'keywords': ['حادث', 'سقوط', 'جرح', 'trauma'], 'steps': ['ABC', 'تصوير سريع', 'تحضير غرفة العمليات']}
        ]
        active = EmergencyCase.query.filter(
            EmergencyCase.status.in_([EmergencyStatus.WAITING, EmergencyStatus.TRIAGE, EmergencyStatus.RESUSCITATION, EmergencyStatus.TREATMENT, EmergencyStatus.OBSERVATION])
        ).order_by(EmergencyCase.created_at.desc()).limit(50).all()
        matched_map = {}
        for c in active:
            complaint = (c.chief_complaint or '').lower()
            for p in protocols:
                if any(k in complaint for k in p['keywords']):
                    pid = p['id']
                    if pid not in matched_map:
                        matched_map[pid] = {k: v for k, v in p.items() if k != 'keywords'}
                        matched_map[pid]['usage_count'] = 0
                    matched_map[pid]['usage_count'] += 1
                    break
        active_protocols = list(matched_map.values())
        total_usage = sum(p.get('usage_count', 0) for p in active_protocols)
        return {
            'active_protocols': active_protocols,
            'active_protocols_count': len(active_protocols),
            'total_usage': total_usage
        }
    except Exception:
        return {'active_protocols': [], 'active_protocols_count': 0, 'total_usage': 0}

def get_ems_metrics():
    try:
        now = datetime.now(timezone.utc)
        start_7d = now - timedelta(days=7)
        start_today = datetime.combine(date.today(), datetime.min.time())
        today = now.replace(tzinfo=None) if now.tzinfo else now
        if isinstance(start_today, datetime) and start_today.tzinfo is None and today.tzinfo:
            start_today = start_today.replace(tzinfo=today.tzinfo)
        ems_cases = EmergencyCase.query.filter(
            EmergencyCase.case_number.like('EMS-%'),
            EmergencyCase.created_at >= start_7d
        ).count()
        today_responses = EmergencyCase.query.filter(
            EmergencyCase.created_at >= start_today
        ).count()
        completed = EmergencyCase.query.filter(
            EmergencyCase.status == EmergencyStatus.COMPLETED,
            EmergencyCase.created_at >= start_7d
        ).count()
        total_cases = EmergencyCase.query.filter(
            EmergencyCase.created_at >= start_7d
        ).count()
        diagnosis_accuracy = round((completed / max(total_cases, 1)) * 100, 1)
        active_transports = EmergencyCase.query.filter(
            EmergencyCase.case_number.like('EMS-%'),
            EmergencyCase.status.in_([EmergencyStatus.WAITING, EmergencyStatus.TRIAGE, EmergencyStatus.RESUSCITATION, EmergencyStatus.TREATMENT, EmergencyStatus.OBSERVATION])
        ).all()
        transport_list = []
        for t in active_transports:
            transport_list.append({'id': t.id, 'status': t.status or 'ACTIVE', 'patient_name': t.patient.full_name if t.patient else ''})
        return {
            'ems_cases_7d': int(ems_cases or 0),
            'diagnosis_accuracy': diagnosis_accuracy,
            'patient_satisfaction': 85.0,
            'active_transports': transport_list,
            'today_responses': int(today_responses or 0),
            'avg_response_time': 0
        }
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


# ═══════════════════════════════════════
# SUBMODULE IMPORTS
# ═══════════════════════════════════════

from . import dashboard
from . import queue
from . import treatment
from . import patients
from . import orders
from . import cases
from . import reports
from . import api
from . import analytics
