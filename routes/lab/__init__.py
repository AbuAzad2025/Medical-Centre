"""
Ù…Ø³Ø§Ø±Ø§Øª Ø§Ù„Ù…Ø®ØªØ¨Ø± - Laboratory Routes
Medical System Laboratory Routes
"""

import base64 as base64
import json as json
import logging
from datetime import UTC, date, datetime, timedelta
from datetime import timezone as timezone
from io import BytesIO as BytesIO

import qrcode as qrcode
from flask import Blueprint
from flask import flash as flash
from flask import jsonify as jsonify
from flask import make_response as make_response
from flask import redirect as redirect
from flask import render_template as render_template
from flask import request as request
from flask import send_file as send_file
from flask import url_for as url_for
from flask_login import current_user
from flask_login import login_required as login_required
from sqlalchemy import func, select

from app.extensions import db
from app.shared.enums import LabResultStatus, OrderState
from models.audit_trail import AuditTrail as AuditTrail
from models.lab_quality import LabQualityControlEntry
from models.lab_reagent import LabReagent as LabReagent
from models.lab_request import LabRequest, LabResult
from models.patient import Patient as Patient
from models.user import User as User
from models.visit import Visit as Visit
from utils.db_safety import safe_commit as safe_commit
from utils.db_safety import safe_rollback
from utils.decorators import role_required as role_required

lab_bp = Blueprint('lab', __name__)

from services.feature_gate_service import guard_module


@lab_bp.before_request
def _guard_lab_module():
    guard_module('lab')


def _log_lab_workflow(request_id, status, action, notes=None):
    try:
        from models.request_workflow import RequestWorkflow

        db.session.add(
            RequestWorkflow(
                request_id=request_id,
                request_type='lab',
                department='lab',
                status=status,
                action=action,
                notes=notes,
                timestamp=datetime.now(UTC),
                user_id=getattr(current_user, 'id', None) or 0,
            )
        )
    except Exception as e:
        logging.warning(f'Error in {__name__}: {e}')


def get_lab_smart_analytics():
    """Ø§Ù„ØªØ­Ù„ÙŠÙ„Ø§Øª Ø§Ù„Ø°ÙƒÙŠØ© Ù„Ù„Ù…Ø®ØªØ¨Ø±"""
    try:
        total_requests = db.session.execute(select(func.count()).select_from(LabRequest)).scalar()
        completed_requests = db.session.execute(
            select(func.count())
            .select_from(LabRequest)
            .filter(LabRequest.status == OrderState.DONE)
        ).scalar()
        pending_requests = db.session.execute(
            select(func.count())
            .select_from(LabRequest)
            .filter(
                LabRequest.status.in_(
                    [
                        OrderState.REQUESTED,
                        OrderState.COLLECTED,
                        OrderState.RECEIVED,
                        OrderState.ANALYZING,
                        OrderState.REVIEWED,
                        OrderState.APPROVED,
                        OrderState.IN_PROGRESS,
                    ]
                )
            )
        ).scalar()
        completion_rate = (completed_requests / total_requests * 100) if total_requests > 0 else 0
        try:
            avg_processing_seconds = db.session.execute(
                select(
                    db.func.avg(
                        db.func.extract('epoch', LabRequest.completed_at)
                        - db.func.extract('epoch', LabRequest.created_at)
                    )
                ).filter(LabRequest.status == OrderState.DONE, LabRequest.completed_at.isnot(None))
            ).scalar()
        except Exception:
            safe_rollback(db.session, error_message='database rollback')
            avg_processing_seconds = None
        avg_processing_time = round((float(avg_processing_seconds or 0) / 3600.0), 2)
        return {
            'total_requests': total_requests,
            'completion_rate': round(completion_rate, 2),
            'pending_requests': pending_requests,
            'avg_processing_time': avg_processing_time,
            'efficiency_score': calculate_lab_efficiency(completion_rate, pending_requests),
            'status': 'excellent'
            if completion_rate > 90
            else 'good'
            if completion_rate > 70
            else 'needs_improvement',
        }
    except Exception as e:
        logging.debug(f'Error getting lab smart analytics: {e!s}')
        return {}


def get_lab_test_optimization():
    """ØªØ­Ø³ÙŠÙ† Ø§Ù„ÙØ­ÙˆØµØ§Øª"""
    try:
        total_requests = db.session.execute(select(func.count()).select_from(LabRequest)).scalar()
        try:
            avg_processing_seconds = db.session.execute(
                select(
                    db.func.avg(
                        db.func.extract('epoch', LabRequest.completed_at)
                        - db.func.extract('epoch', LabRequest.created_at)
                    )
                ).filter(LabRequest.status == OrderState.DONE, LabRequest.completed_at.isnot(None))
            ).scalar()
        except Exception:
            safe_rollback(db.session, error_message='database rollback')
            avg_processing_seconds = None
        avg_processing_time = round((float(avg_processing_seconds or 0) / 3600.0), 2)
        total_processed = db.session.execute(
            select(func.count())
            .select_from(LabRequest)
            .filter(LabRequest.status == OrderState.DONE)
        ).scalar()
        suggestions = generate_optimization_suggestions(avg_processing_time)
        return {
            'avg_processing_time': avg_processing_time,
            'total_processed': total_processed,
            'optimization_suggestions': suggestions,
            'efficiency_score': calculate_test_efficiency(avg_processing_time, total_requests),
        }
    except Exception as e:
        logging.debug(f'Error getting lab test optimization: {e!s}')
        return {}


def get_lab_quality_control():
    """Ù…Ø±Ø§Ù‚Ø¨Ø© Ø§Ù„Ø¬ÙˆØ¯Ø©"""
    try:
        total_completed = db.session.execute(
            select(func.count())
            .select_from(LabRequest)
            .filter(LabRequest.status == OrderState.DONE)
        ).scalar()
        qc_total = db.session.execute(
            select(func.count()).select_from(LabQualityControlEntry)
        ).scalar()
        qc_fail = db.session.execute(
            select(func.count())
            .select_from(LabQualityControlEntry)
            .filter(LabQualityControlEntry.status == 'FAIL')
        ).scalar()
        quality_score = 100.0 - (float(qc_fail) / float(qc_total) * 100.0) if qc_total else 100.0
        standard_deviations = round((qc_fail / qc_total) * 3, 2) if qc_total else 0
        recheck_requests = db.session.execute(
            select(func.count())
            .select_from(LabRequest)
            .filter(LabRequest.status == OrderState.REVIEWED)
        ).scalar()
        return {
            'total_completed': total_completed,
            'quality_score': round(quality_score, 2),
            'standard_deviations': standard_deviations,
            'recheck_requests': recheck_requests,
        }
    except Exception:
        logging.exception('Error getting lab quality control: %s')
        return {}


def get_lab_equipment_monitoring():
    """Ù…Ø±Ø§Ù‚Ø¨Ø© Ø§Ù„Ù…Ø¹Ø¯Ø§Øª"""
    try:
        equipment_status = {
            'analyzers': 'operational',
            'centrifuges': 'operational',
            'microscopes': 'operational',
            'incubators': 'maintenance',
        }
        total_equipment = len(equipment_status)
        operational = len([v for v in equipment_status.values() if v == 'operational'])
        maintenance = len([v for v in equipment_status.values() if v == 'maintenance'])
        efficiency = round((operational / total_equipment) * 100, 2) if total_equipment else 0
        return {
            'total_equipment': total_equipment,
            'operational': operational,
            'maintenance': maintenance,
            'efficiency': efficiency,
        }
    except Exception:
        logging.exception('Error getting lab equipment monitoring: %s')
        return {}


def get_lab_result_analysis():
    """ØªØ­Ù„ÙŠÙ„ Ø§Ù„Ù†ØªØ§Ø¦Ø¬"""
    try:
        total_results = db.session.execute(select(func.count()).select_from(LabResult)).scalar()
        abnormal_results = db.session.execute(
            select(func.count())
            .select_from(LabResult)
            .filter(
                LabResult.is_critical,
                LabResult.status.in_([LabResultStatus.READY, LabResultStatus.VALIDATED]),
            )
        ).scalar()
        abnormal_rate = (abnormal_results / total_results * 100) if total_results else 0
        today = date.today()
        last_7 = db.session.execute(
            select(func.count())
            .select_from(LabResult)
            .filter(LabResult.created_at >= (today - timedelta(days=7)))
        ).scalar()
        prev_7 = db.session.execute(
            select(func.count())
            .select_from(LabResult)
            .filter(
                LabResult.created_at >= (today - timedelta(days=14)),
                LabResult.created_at < (today - timedelta(days=7)),
            )
        ).scalar()
        trend_analysis = (
            'ØªØµØ§Ø¹Ø¯ÙŠ'
            if last_7 > prev_7
            else 'ØªÙ†Ø§Ø²Ù„ÙŠ'
            if last_7 < prev_7
            else 'Ù…Ø³ØªÙ‚Ø±'
        )
        return {
            'total_results': total_results,
            'abnormal_results': abnormal_results,
            'abnormal_rate': round(abnormal_rate, 2),
            'trend_analysis': trend_analysis,
        }
    except Exception:
        logging.exception('Error getting lab result analysis: %s')
        return {}


def get_lab_workflow_automation():
    """Ø£ØªÙ…ØªØ© Ø³ÙŠØ± Ø§Ù„Ø¹Ù…Ù„"""
    try:
        total_requests = db.session.execute(select(func.count()).select_from(LabRequest)).scalar()
        done_requests = db.session.execute(
            select(func.count())
            .select_from(LabRequest)
            .filter(LabRequest.status == OrderState.DONE)
        ).scalar()
        automation_rate = round((done_requests / total_requests) * 100, 2) if total_requests else 0
        automated_tasks = done_requests
        time_saved = round(automation_rate * 1.2, 2)
        efficiency_gain = round(automation_rate * 0.8, 2)
        return {
            'automated_tasks': automated_tasks,
            'automation_rate': automation_rate,
            'time_saved': time_saved,
            'efficiency_gain': efficiency_gain,
        }
    except Exception:
        logging.exception('Error getting lab workflow automation: %s')
        return {}


def get_lab_predictive_insights():
    try:
        today = date.today()
        week_start = today - timedelta(days=7)
        month_start = today - timedelta(days=30)
        weekly_requests = db.session.execute(
            select(func.count()).select_from(LabRequest).filter(LabRequest.created_at >= week_start)
        ).scalar()
        monthly_requests = db.session.execute(
            select(func.count())
            .select_from(LabRequest)
            .filter(LabRequest.created_at >= month_start)
        ).scalar()
        prev_week = db.session.execute(
            select(func.count())
            .select_from(LabRequest)
            .filter(
                LabRequest.created_at >= today - timedelta(days=14),
                LabRequest.created_at < week_start,
            )
        ).scalar()
        growth_rate = ((weekly_requests - prev_week) / prev_week * 100) if prev_week else 0
        predicted_demand = round((weekly_requests / 7) * 7)
        return {
            'weekly_requests': weekly_requests,
            'monthly_requests': monthly_requests,
            'predicted_demand': predicted_demand,
            'growth_rate': round(growth_rate, 2),
        }
    except Exception:
        return {}


def calculate_lab_efficiency(completion_rate, pending_requests):
    """Ø­Ø³Ø§Ø¨ ÙƒÙØ§Ø¡Ø© Ø§Ù„Ù…Ø®ØªØ¨Ø±"""
    try:
        base_score = completion_rate
        penalty = min(pending_requests * 2, 20)  # Ø®ØµÙ… Ù„ÙƒÙ„ Ø·Ù„Ø¨ Ù…Ø¹Ù„Ù‚
        return max(base_score - penalty, 0)
    except (TypeError, ValueError):
        return 0


def calculate_test_efficiency(avg_time, total_tests):
    """Ø­Ø³Ø§Ø¨ ÙƒÙØ§Ø¡Ø© Ø§Ù„ÙØ­ÙˆØµØ§Øª"""
    try:
        if avg_time <= 2:  # Ø³Ø§Ø¹ØªØ§Ù† Ø£Ùˆ Ø£Ù‚Ù„
            return 95
        if avg_time <= 4:  # 4 Ø³Ø§Ø¹Ø§Øª Ø£Ùˆ Ø£Ù‚Ù„
            return 85
        if avg_time <= 6:  # 6 Ø³Ø§Ø¹Ø§Øª Ø£Ùˆ Ø£Ù‚Ù„
            return 75
        return 60
    except (TypeError, ValueError):
        return 0


def generate_optimization_suggestions(avg_time):
    """ØªÙˆÙ„ÙŠØ¯ Ø§Ù‚ØªØ±Ø§Ø­Ø§Øª Ø§Ù„ØªØ­Ø³ÙŠÙ†"""
    suggestions = []

    if avg_time > 4:
        suggestions.append('ØªØ­Ø³ÙŠÙ† ØªØ¯ÙÙ‚ Ø§Ù„Ø¹ÙŠÙ†Ø§Øª')
    if avg_time > 6:
        suggestions.append('Ø¥Ø¶Ø§ÙØ© Ù…Ø¹Ø¯Ø§Øª Ø¬Ø¯ÙŠØ¯Ø©')
    if avg_time > 8:
        suggestions.append('Ø²ÙŠØ§Ø¯Ø© Ø¹Ø¯Ø¯ Ø§Ù„ÙÙ†ÙŠÙŠÙ†')

    return suggestions


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# SUBMODULE IMPORTS
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

from . import barcode as barcode
from . import dashboard as dashboard
from . import fhir as fhir
from . import lis_import as lis_import
from . import quality as quality
from . import reagents as reagents
from . import reports as reports
from . import test_catalog as test_catalog
from . import worklist as worklist
