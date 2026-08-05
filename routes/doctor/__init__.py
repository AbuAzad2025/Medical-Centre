import json as json
import logging as logging
import secrets
from datetime import UTC, datetime
from datetime import date as date
from datetime import timedelta as timedelta
from datetime import timezone as timezone

from flask import Blueprint, redirect, url_for
from flask import current_app as current_app
from flask import flash as flash
from flask import jsonify as jsonify
from flask import render_template as render_template
from flask import request as request
from flask_login import current_user, login_required
from sqlalchemy import and_ as and_
from sqlalchemy import case as case
from sqlalchemy import desc as desc
from sqlalchemy import func as func
from sqlalchemy import or_ as or_
from sqlalchemy import select

from app.extensions import db
from app.shared.enums import AppointmentState
from models.appointment import Appointment as Appointment
from models.audit_trail import AuditTrail as AuditTrail
from models.department import Department as Department
from models.drug_interaction import DrugInteraction as DrugInteraction
from models.follow_up import FollowUpRequest
from models.lab_request import LabRequest as LabRequest
from models.medical_record import MedicalRecord as MedicalRecord
from models.medication import Prescription as Prescription
from models.patient import Patient as Patient
from models.radiology_request import RadiologyRequest as RadiologyRequest
from models.system_config import SystemConfig
from models.user import User as User
from models.visit import Visit
from utils.db_safety import safe_commit, safe_rollback
from utils.decorators import role_required as role_required
from utils.decorators import role_required_json as role_required_json

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
    return (
        db.session.execute(
            select(SystemConfig)
            .filter_by(config_key='doctor_note_templates')
            .filter(SystemConfig.tenant_id == current_user.tenant_id)
        )
        .scalars()
        .first()
    )


def _default_doctor_note_templates():
    return [
        {
            'id': secrets.token_hex(8),
            'name': 'SOAP قالب',
            'text': 'S:\nO:\nA:\nP:\n',
            'is_active': True,
        },
        {
            'id': secrets.token_hex(8),
            'name': 'تعليمات خروج',
            'text': 'تعليمات للمريض:\n- \n- \n',
            'is_active': True,
        },
        {
            'id': secrets.token_hex(8),
            'name': 'متابعة',
            'text': 'يوصى بالمتابعة خلال ____ أيام.\nعلامات إنذار: ________\n',
            'is_active': True,
        },
    ]


def _get_doctor_note_templates():
    cfg = _doctor_note_templates_cfg()
    if not cfg:
        cfg = SystemConfig(
            config_key='doctor_note_templates',
            tenant_id=current_user.tenant_id,
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
        try:
            safe_commit(db.session, error_message='database commit failed', reraise=True)
        except Exception:
            safe_rollback(db.session, error_message='database rollback')
            raise
        return templates

    templates = cfg.get_value() if cfg.config_type == 'json' else []
    if not isinstance(templates, list):
        templates = []
    if not templates:
        templates = _default_doctor_note_templates()
        cfg.set_value(templates)
        cfg.updated_by = getattr(current_user, 'id', None)
        try:
            safe_commit(db.session, error_message='database commit failed', reraise=True)
        except Exception:
            safe_rollback(db.session, error_message='database rollback')
            raise
    return templates


def _save_doctor_note_templates(templates):
    cfg = _doctor_note_templates_cfg()
    if not cfg:
        cfg = SystemConfig(
            config_key='doctor_note_templates',
            tenant_id=current_user.tenant_id,
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
    try:
        safe_commit(db.session, error_message='database commit failed', reraise=True)
    except Exception:
        safe_rollback(db.session, error_message='database rollback')
        raise


def _doctor_dashboard_layout_cfg_key():
    return f'doctor_dashboard_layout_{current_user.id}'


def _default_doctor_dashboard_layout():
    return [
        {'id': 'stats_overview', 'title': 'الإحصائيات السريعة', 'order': 1, 'enabled': True},
        {'id': 'patients_actions', 'title': 'المرضى والإجراءات', 'order': 2, 'enabled': True},
        {'id': 'smart_insights', 'title': 'الدعم الذكي والتحليلات', 'order': 3, 'enabled': True},
    ]


def _get_doctor_dashboard_layout():
    cfg = (
        db.session.execute(
            select(SystemConfig)
            .filter_by(config_key=_doctor_dashboard_layout_cfg_key())
            .filter(SystemConfig.tenant_id == current_user.tenant_id)
        )
        .scalars()
        .first()
    )
    if not cfg:
        cfg = SystemConfig(
            config_key=_doctor_dashboard_layout_cfg_key(),
            tenant_id=current_user.tenant_id,
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
        try:
            safe_commit(db.session, error_message='database commit failed', reraise=True)
        except Exception:
            safe_rollback(db.session, error_message='database rollback')
            raise
        return layout
    layout = cfg.get_value() if cfg.config_type == 'json' else []
    if not isinstance(layout, list) or not layout:
        layout = _default_doctor_dashboard_layout()
        cfg.config_type = 'json'
        cfg.set_value(layout)
        cfg.updated_by = getattr(current_user, 'id', None)
        try:
            safe_commit(db.session, error_message='database commit failed', reraise=True)
        except Exception:
            safe_rollback(db.session, error_message='database rollback')
            raise
    return layout


def _save_doctor_dashboard_layout(items):
    cfg = (
        db.session.execute(
            select(SystemConfig)
            .filter_by(config_key=_doctor_dashboard_layout_cfg_key())
            .filter(SystemConfig.tenant_id == current_user.tenant_id)
        )
        .scalars()
        .first()
    )
    if not cfg:
        cfg = SystemConfig(
            config_key=_doctor_dashboard_layout_cfg_key(),
            tenant_id=current_user.tenant_id,
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
    try:
        safe_commit(db.session, error_message='database commit failed', reraise=True)
    except Exception:
        safe_rollback(db.session, error_message='database rollback')
        raise


def _sync_follow_up_request_for_visit(visit: Visit, actor_user_id: int):
    suggested = getattr(visit, 'follow_up_date', None)
    required = bool(getattr(visit, 'follow_up_required', False))
    tid = visit.tenant_id
    if required and suggested:
        existing = (
            db.session.execute(
                select(FollowUpRequest)
                .filter(
                    FollowUpRequest.source_visit_id == visit.id, FollowUpRequest.tenant_id == tid
                )
                .order_by(FollowUpRequest.created_at.desc())
            )
            .scalars()
            .first()
        )
        if existing and existing.status in {'CANCELLED', 'DONE'}:
            existing = None
        if existing:
            existing.patient_id = visit.patient_id
            existing.doctor_id = visit.doctor_id
            existing.suggested_date = suggested
            existing.notes = getattr(visit, 'follow_up_notes', None) or existing.notes
            existing.status = (
                existing.status if existing.status == AppointmentState.SCHEDULED else 'PENDING'
            )
            existing.updated_at = datetime.now(UTC)
        else:
            db.session.add(
                FollowUpRequest(
                    tenant_id=tid,
                    patient_id=visit.patient_id,
                    doctor_id=visit.doctor_id,
                    source_visit_id=visit.id,
                    suggested_date=suggested,
                    notes=getattr(visit, 'follow_up_notes', None),
                    status='PENDING',
                    created_by=actor_user_id,
                )
            )
        return

    existing = (
        db.session.execute(
            select(FollowUpRequest)
            .filter(FollowUpRequest.source_visit_id == visit.id, FollowUpRequest.tenant_id == tid)
            .order_by(FollowUpRequest.created_at.desc())
        )
        .scalars()
        .first()
    )
    if existing and existing.status in {'PENDING'}:
        existing.status = 'CANCELLED'
        existing.updated_at = datetime.now(UTC)


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

from . import appointments as appointments
from . import dashboard as dashboard
from . import diagnosis as diagnosis
from . import lab as lab
from . import notes as notes
from . import patients as patients
from . import prescriptions as prescriptions
from . import queue as queue
from . import radiology as radiology
from . import visits as visits
