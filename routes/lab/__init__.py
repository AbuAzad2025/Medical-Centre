"""
مسارات المختبر - Laboratory Routes
Medical System Laboratory Routes
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, send_file, make_response
from flask_login import login_required, current_user
from utils.decorators import role_required
from models.patient import Patient
from models.visit import Visit
from models.user import User
from models.lab_request import LabRequest
from models.lab_request import LabResult
from models.lab_quality import LabQualityControlEntry
from models.lab_reagent import LabReagent
from models.audit_trail import AuditTrail
from app_factory import db
import logging
from datetime import datetime, date, timezone, timedelta
import json
import base64
from io import BytesIO
import qrcode

lab_bp = Blueprint('lab', __name__)

from services.feature_gate_service import guard_module

@lab_bp.before_request
def _guard_lab_module():
    guard_module('lab')

def _log_lab_workflow(request_id, status, action, notes=None):
    try:
        from models.request_workflow import RequestWorkflow
        db.session.add(RequestWorkflow(
            request_id=request_id,
            request_type='lab',
            department='lab',
            status=status,
            action=action,
            notes=notes,
            timestamp=datetime.now(timezone.utc),
            user_id=getattr(current_user, 'id', None) or 0
        ))
    except Exception as e:
        logging.warning(f"Error in {__name__}: {e}")
def get_lab_smart_analytics():
    """التحليلات الذكية للمختبر"""
    try:
        total_requests = LabRequest.query.count()
        completed_requests = LabRequest.query.filter(LabRequest.status == OrderState.DONE).count()
        pending_requests = LabRequest.query.filter(
            LabRequest.status.in_([OrderState.REQUESTED, OrderState.COLLECTED, OrderState.RECEIVED, OrderState.ANALYZING, OrderState.REVIEWED, OrderState.APPROVED, OrderState.IN_PROGRESS])
        ).count()
        completion_rate = (completed_requests / total_requests * 100) if total_requests > 0 else 0
        try:
            avg_processing_seconds = db.session.query(
                db.func.avg(db.func.extract('epoch', LabRequest.completed_at) - db.func.extract('epoch', LabRequest.created_at))
            ).filter(LabRequest.status == OrderState.DONE, LabRequest.completed_at.isnot(None)).scalar()
        except Exception:
            db.session.rollback()
            avg_processing_seconds = None
        avg_processing_time = round((float(avg_processing_seconds or 0) / 3600.0), 2)
        return {
            'total_requests': total_requests,
            'completion_rate': round(completion_rate, 2),
            'pending_requests': pending_requests,
            'avg_processing_time': avg_processing_time,
            'efficiency_score': calculate_lab_efficiency(completion_rate, pending_requests),
            'status': 'excellent' if completion_rate > 90 else 'good' if completion_rate > 70 else 'needs_improvement'
        }
    except Exception as e:
        logging.debug(f"Error getting lab smart analytics: {str(e)}")
        return {}

def get_lab_test_optimization():
    """تحسين الفحوصات"""
    try:
        total_requests = LabRequest.query.count()
        try:
            avg_processing_seconds = db.session.query(
                db.func.avg(db.func.extract('epoch', LabRequest.completed_at) - db.func.extract('epoch', LabRequest.created_at))
            ).filter(LabRequest.status == OrderState.DONE, LabRequest.completed_at.isnot(None)).scalar()
        except Exception:
            db.session.rollback()
            avg_processing_seconds = None
        avg_processing_time = round((float(avg_processing_seconds or 0) / 3600.0), 2)
        total_processed = LabRequest.query.filter(LabRequest.status == OrderState.DONE).count()
        suggestions = generate_optimization_suggestions(avg_processing_time)
        return {
            'avg_processing_time': avg_processing_time,
            'total_processed': total_processed,
            'optimization_suggestions': suggestions,
            'efficiency_score': calculate_test_efficiency(avg_processing_time, total_requests)
        }
    except Exception as e:
        logging.debug(f"Error getting lab test optimization: {str(e)}")
        return {}

def get_lab_quality_control():
    """مراقبة الجودة"""
    try:
        total_completed = LabRequest.query.filter(LabRequest.status == OrderState.DONE).count()
        qc_total = LabQualityControlEntry.query.count()
        qc_fail = LabQualityControlEntry.query.filter(LabQualityControlEntry.status == 'FAIL').count()
        quality_score = 100.0 - (float(qc_fail) / float(qc_total) * 100.0) if qc_total else 100.0
        standard_deviations = round((qc_fail / qc_total) * 3, 2) if qc_total else 0
        recheck_requests = LabRequest.query.filter(LabRequest.status == OrderState.REVIEWED).count()
        return {
            'total_completed': total_completed,
            'quality_score': round(quality_score, 2),
            'standard_deviations': standard_deviations,
            'recheck_requests': recheck_requests
        }
    except Exception as e:
        logging.error(f"Error getting lab quality control: {str(e)}")
        return {}

def get_lab_equipment_monitoring():
    """مراقبة المعدات"""
    try:
        equipment_status = {
            'analyzers': 'operational',
            'centrifuges': 'operational',
            'microscopes': 'operational',
            'incubators': 'maintenance'
        }
        total_equipment = len(equipment_status)
        operational = len([v for v in equipment_status.values() if v == 'operational'])
        maintenance = len([v for v in equipment_status.values() if v == 'maintenance'])
        efficiency = round((operational / total_equipment) * 100, 2) if total_equipment else 0
        return {
            'total_equipment': total_equipment,
            'operational': operational,
            'maintenance': maintenance,
            'efficiency': efficiency
        }
    except Exception as e:
        logging.error(f"Error getting lab equipment monitoring: {str(e)}")
        return {}

def get_lab_result_analysis():
    """تحليل النتائج"""
    try:
        total_results = LabResult.query.count()
        abnormal_results = LabResult.query.filter(
            LabResult.is_critical == True,
            LabResult.status.in_([LabResultStatus.READY, LabResultStatus.VALIDATED])
        ).count()
        abnormal_rate = (abnormal_results / total_results * 100) if total_results else 0
        today = date.today()
        last_7 = LabResult.query.filter(LabResult.created_at >= (today - timedelta(days=7))).count()
        prev_7 = LabResult.query.filter(
            LabResult.created_at >= (today - timedelta(days=14)),
            LabResult.created_at < (today - timedelta(days=7))
        ).count()
        trend_analysis = 'تصاعدي' if last_7 > prev_7 else 'تنازلي' if last_7 < prev_7 else 'مستقر'
        return {
            'total_results': total_results,
            'abnormal_results': abnormal_results,
            'abnormal_rate': round(abnormal_rate, 2),
            'trend_analysis': trend_analysis
        }
    except Exception as e:
        logging.error(f"Error getting lab result analysis: {str(e)}")
        return {}

def get_lab_workflow_automation():
    """أتمتة سير العمل"""
    try:
        total_requests = LabRequest.query.count()
        done_requests = LabRequest.query.filter(LabRequest.status == OrderState.DONE).count()
        automation_rate = round((done_requests / total_requests) * 100, 2) if total_requests else 0
        automated_tasks = done_requests
        time_saved = round(automation_rate * 1.2, 2)
        efficiency_gain = round(automation_rate * 0.8, 2)
        return {
            'automated_tasks': automated_tasks,
            'automation_rate': automation_rate,
            'time_saved': time_saved,
            'efficiency_gain': efficiency_gain
        }
    except Exception as e:
        logging.error(f"Error getting lab workflow automation: {str(e)}")
        return {}

def get_lab_predictive_insights():
    try:
        today = date.today()
        week_start = today - timedelta(days=7)
        month_start = today - timedelta(days=30)
        weekly_requests = LabRequest.query.filter(LabRequest.created_at >= week_start).count()
        monthly_requests = LabRequest.query.filter(LabRequest.created_at >= month_start).count()
        prev_week = LabRequest.query.filter(
            LabRequest.created_at >= today - timedelta(days=14),
            LabRequest.created_at < week_start
        ).count()
        growth_rate = ((weekly_requests - prev_week) / prev_week * 100) if prev_week else 0
        predicted_demand = int(round((weekly_requests / 7) * 7))
        return {
            'weekly_requests': weekly_requests,
            'monthly_requests': monthly_requests,
            'predicted_demand': predicted_demand,
            'growth_rate': round(growth_rate, 2)
        }
    except Exception:
        return {}

def calculate_lab_efficiency(completion_rate, pending_requests):
    """حساب كفاءة المختبر"""
    try:
        base_score = completion_rate
        penalty = min(pending_requests * 2, 20)  # خصم لكل طلب معلق
        return max(base_score - penalty, 0)
    except:
        return 0

def calculate_test_efficiency(avg_time, total_tests):
    """حساب كفاءة الفحوصات"""
    try:
        if avg_time <= 2:  # ساعتان أو أقل
            return 95
        elif avg_time <= 4:  # 4 ساعات أو أقل
            return 85
        elif avg_time <= 6:  # 6 ساعات أو أقل
            return 75
        else:
            return 60
    except:
        return 0

def generate_optimization_suggestions(avg_time):
    """توليد اقتراحات التحسين"""
    suggestions = []
    
    if avg_time > 4:
        suggestions.append("تحسين تدفق العينات")
    if avg_time > 6:
        suggestions.append("إضافة معدات جديدة")
    if avg_time > 8:
        suggestions.append("زيادة عدد الفنيين")
    
    return suggestions

# ═══════════════════════════════════════
# SUBMODULE IMPORTS
# ═══════════════════════════════════════

from . import dashboard
from . import worklist
from . import reagents
from . import quality
from . import reports
from . import fhir
from . import test_catalog
from . import barcode
