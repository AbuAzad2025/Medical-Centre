 

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
from app.shared.enums import AppointmentState

from models.system_config import SystemConfig

doctor_bp = Blueprint('doctor', __name__)

from services.feature_gate_service import guard_module

@doctor_bp.before_request
def _guard_doctor_module():
    guard_module('doctor')

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
            category='general',
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
            category='general',
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
            existing.status = existing.status if existing.status == AppointmentState.SCHEDULED else 'PENDING'
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






































def calculate_medical_performance_score(completion_rate, avg_duration):
    """حساب نقاط الأداء الطبي"""
    # نقاط الإنجاز
    completion_score = completion_rate
    
    # نقاط الكفاءة (كلما قل الوقت كلما زادت النقاط)
    efficiency_score = max(0, 100 - (avg_duration / 60 * 20))
    
    return (completion_score + efficiency_score) / 2


# ═══════════════════════════════════════
# SUBMODULE IMPORTS
# ═══════════════════════════════════════

from . import dashboard
from . import queue
from . import visits
from . import diagnosis
from . import prescriptions
from . import lab
from . import radiology
from . import notes
from . import patients
from . import appointments
