"""
مسارات الأشعة - Radiology Routes
Medical System Radiology Routes
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, send_file, current_app
from flask_login import login_required, current_user
from utils.decorators import role_required
from models.patient import Patient
from models.visit import Visit
from models.user import User
from models.radiology_request import RadiologyRequest
from models.radiology_result import RadiologyResult
from models.file_management import FileUpload
from models.system_config import SystemConfig
from app_factory import db
import logging
from datetime import datetime, date, timezone
from datetime import timedelta
import json
import os
from werkzeug.utils import secure_filename
import base64
from io import BytesIO
import qrcode
import secrets

radiology_bp = Blueprint('radiology', __name__, guard_module=__name__)

from services.feature_gate_service import guard_module

@radiology_bp.before_request
def _guard_radiology_module():
    guard_module('radiology')

def _log_radiology_workflow(request_id, status, action, notes=None):
    try:
        from models.request_workflow import RequestWorkflow
        db.session.add(RequestWorkflow(
            request_id=request_id,
            request_type='radiology',
            department='radiology',
            status=status,
            action=action,
            notes=notes,
            timestamp=datetime.now(timezone.utc),
            user_id=getattr(current_user, 'id', None) or 0
        ))
    except Exception as e:

        logging.warning(f"Error in {__name__}: {e}")
def _radiology_templates_cfg():
    return SystemConfig.query.filter_by(config_key='radiology_report_templates').first()

def _radiology_macros_cfg():
    return SystemConfig.query.filter_by(config_key='radiology_report_macros').first()

def _default_radiology_report_templates():
    return [
        {
            'id': secrets.token_hex(8),
            'name': 'X-Ray قالب عام',
            'modality': 'XRAY',
            'findings': "الطريقة (Technique):\nأشعة سينية لـ {{BODY_PART}} (Views: ________)\n\nالموجودات (Findings):\n- العظام/المفاصل: ________________________\n- النسج الرخوة: _________________________\n- ملاحظات إضافية: _______________________\n",
            'impression': "الخلاصة (Impression):\n1) ________________________\n2) ________________________\n",
            'recommendations': "التوصيات:\n- ربط النتائج بالسياق السريري.\n- متابعة/تصوير إضافي عند الحاجة.\n",
            'is_active': True
        },
        {
            'id': secrets.token_hex(8),
            'name': 'CT قالب عام',
            'modality': 'CT',
            'findings': "الطريقة (Technique):\nCT لـ {{BODY_PART}} (مع/بدون مادة ظليلة: ________) (Slice thickness: ________)\n\nالموجودات (Findings):\n- الأعضاء/البنى ذات الصلة: ________________________\n- العقد/السوائل/النزف: ___________________________\n- ملاحظات إضافية: _______________________________\n",
            'impression': "الخلاصة (Impression):\n1) ________________________\n2) ________________________\n",
            'recommendations': "التوصيات:\n- ربط النتائج بالسياق السريري.\n- متابعة/استشارة اختصاصية عند الحاجة.\n",
            'is_active': True
        },
        {
            'id': secrets.token_hex(8),
            'name': 'MRI قالب عام',
            'modality': 'MRI',
            'findings': "الطريقة (Technique):\nMRI لـ {{BODY_PART}} (Sequences: ________) (مع/بدون مادة ظليلة: ________)\n\nالموجودات (Findings):\n- التغيرات البنيوية/الإشارة: ________________________\n- السوائل/الكتل/الآفات: ____________________________\n- ملاحظات إضافية: ________________________________\n",
            'impression': "الخلاصة (Impression):\n1) ________________________\n2) ________________________\n",
            'recommendations': "التوصيات:\n- ربط النتائج بالسياق السريري.\n- متابعة/تصوير إضافي عند الحاجة.\n",
            'is_active': True
        }
    ]

def _default_radiology_report_macros():
    return [
        {'id': secrets.token_hex(8), 'name': 'Normal', 'text': 'لا توجد موجودات حادة. ضمن الحدود الطبيعية.', 'is_active': True},
        {'id': secrets.token_hex(8), 'name': 'Recommend Follow-up', 'text': 'يوصى بالمتابعة وربط النتائج بالسياق السريري.', 'is_active': True},
        {'id': secrets.token_hex(8), 'name': 'Limited Study', 'text': 'الدراسة محدودة بسبب ________. يوصى بإعادة التصوير عند الحاجة.', 'is_active': True},
    ]

def _get_radiology_report_templates():
    cfg = _radiology_templates_cfg()
    if not cfg:
        cfg = SystemConfig(
            config_key='radiology_report_templates',
            config_type='json',
            config_value='[]',
            category='general',
            description='قوالب تقارير الأشعة',
            is_system=False,
            is_encrypted=False,
            created_by=getattr(current_user, 'id', None),
            updated_by=getattr(current_user, 'id', None),
        )
        db.session.add(cfg)
        templates = _default_radiology_report_templates()
        cfg.set_value(templates)
        db.session.commit()
        return templates

    templates = cfg.get_value() if cfg.config_type == 'json' else []
    if not isinstance(templates, list):
        templates = []
    if not templates:
        templates = _default_radiology_report_templates()
        cfg.set_value(templates)
        cfg.updated_by = getattr(current_user, 'id', None)
        db.session.commit()
    return templates

def _save_radiology_report_templates(templates):
    cfg = _radiology_templates_cfg()
    if not cfg:
        cfg = SystemConfig(
            config_key='radiology_report_templates',
            config_type='json',
            config_value='[]',
            category='general',
            description='قوالب تقارير الأشعة',
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

def _get_radiology_report_macros():
    cfg = _radiology_macros_cfg()
    if not cfg:
        cfg = SystemConfig(
            config_key='radiology_report_macros',
            config_type='json',
            config_value='[]',
            category='general',
            description='ماكروز تقارير الأشعة',
            is_system=False,
            is_encrypted=False,
            created_by=getattr(current_user, 'id', None),
            updated_by=getattr(current_user, 'id', None),
        )
        db.session.add(cfg)
        macros = _default_radiology_report_macros()
        cfg.set_value(macros)
        db.session.commit()
        return macros

    macros = cfg.get_value() if cfg.config_type == 'json' else []
    if not isinstance(macros, list):
        macros = []
    if not macros:
        macros = _default_radiology_report_macros()
        cfg.set_value(macros)
        cfg.updated_by = getattr(current_user, 'id', None)
        db.session.commit()
    return macros

def _save_radiology_report_macros(macros):
    cfg = _radiology_macros_cfg()
    if not cfg:
        cfg = SystemConfig(
            config_key='radiology_report_macros',
            config_type='json',
            config_value='[]',
            category='general',
            description='ماكروز تقارير الأشعة',
            is_system=False,
            is_encrypted=False,
            created_by=getattr(current_user, 'id', None),
            updated_by=getattr(current_user, 'id', None),
        )
        db.session.add(cfg)
    if not isinstance(macros, list):
        macros = []
    cfg.config_type = 'json'
    cfg.set_value(macros)
    cfg.updated_by = getattr(current_user, 'id', None)
    db.session.commit()















def get_radiology_smart_analytics():
    """التحليلات الذكية للأشعة"""
    try:
        total_requests = RadiologyRequest.query.count()
        completed_requests = RadiologyRequest.query.filter(RadiologyRequest.status == OrderState.DONE).count()
        pending_requests = RadiologyRequest.query.filter(
            RadiologyRequest.status.in_([OrderState.REQUESTED, OrderState.IN_PROGRESS])
        ).count()
        completion_rate = (completed_requests / total_requests * 100) if total_requests > 0 else 0
        try:
            avg_processing_seconds = db.session.query(
                db.func.avg(db.func.extract('epoch', RadiologyRequest.updated_at) - db.func.extract('epoch', RadiologyRequest.created_at))
            ).filter(RadiologyRequest.status == OrderState.DONE).scalar()
        except Exception:
            db.session.rollback()
            avg_processing_seconds = None
        avg_processing_time = round((float(avg_processing_seconds or 0) / 3600.0), 2)
        return {
            'total_requests': total_requests,
            'completion_rate': round(completion_rate, 2),
            'pending_requests': pending_requests,
            'avg_processing_time': avg_processing_time,
            'efficiency_score': calculate_radiology_efficiency(completion_rate, pending_requests),
            'status': 'excellent' if completion_rate > 90 else 'good' if completion_rate > 70 else 'needs_improvement'
        }
    except Exception as e:
        logging.error(f"Error getting radiology smart analytics: {str(e)}")
        return {}

def get_radiology_imaging_optimization():
    """تحسين التصوير"""
    try:
        total_requests = RadiologyRequest.query.count()
        try:
            avg_processing_seconds = db.session.query(
                db.func.avg(db.func.extract('epoch', RadiologyRequest.updated_at) - db.func.extract('epoch', RadiologyRequest.created_at))
            ).filter(RadiologyRequest.status == OrderState.DONE).scalar()
        except Exception:
            db.session.rollback()
            avg_processing_seconds = None
        avg_imaging_time = round((float(avg_processing_seconds or 0) / 3600.0), 2)
        total_processed = RadiologyRequest.query.filter(RadiologyRequest.status == OrderState.DONE).count()
        suggestions = generate_imaging_optimization_suggestions(avg_imaging_time)
        return {
            'avg_imaging_time': avg_imaging_time,
            'total_processed': total_processed,
            'optimization_suggestions': suggestions,
            'efficiency_score': calculate_imaging_efficiency(avg_imaging_time, total_requests)
        }
    except Exception as e:
        logging.error(f"Error getting radiology imaging optimization: {str(e)}")
        return {}

def get_radiology_quality_assurance():
    """ضمان الجودة"""
    try:
        total_done = RadiologyRequest.query.filter(RadiologyRequest.status == OrderState.DONE).count()
        reviewed = RadiologyResult.query.filter(RadiologyResult.reviewed_at.isnot(None)).count()
        critical = RadiologyResult.query.filter(RadiologyResult.is_critical == True).count()
        quality_score = (reviewed / total_done * 100) if total_done else 100
        return {
            'total_completed': total_done,
            'quality_score': round(quality_score, 2),
            'standard_deviations': round((critical / total_done) * 3, 2) if total_done else 0,
            'recheck_requests': RadiologyResult.query.filter(RadiologyResult.revised_after_review == True).count()
        }
    except Exception as e:
        logging.error(f"Error getting radiology quality assurance: {str(e)}")
        return {}

def get_radiology_equipment_status():
    """حالة المعدات"""
    try:
        equipment_status = {
            'xray_machines': 'operational',
            'ct_scanner': 'operational',
            'mri_machine': 'operational',
            'ultrasound': 'maintenance'
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
        logging.error(f"Error getting radiology equipment status: {str(e)}")
        return {}

def get_radiology_report_analysis():
    """تحليل التقارير"""
    try:
        total_reports = RadiologyResult.query.count()
        abnormal_findings = RadiologyResult.query.filter(
            RadiologyResult.status.in_([LabResultStatus.READY, LabResultStatus.VALIDATED])
        ).count()
        critical_reports = RadiologyResult.query.filter(RadiologyResult.is_critical == True).count()
        abnormal_rate = (abnormal_findings / total_reports * 100) if total_reports else 0
        last_7 = RadiologyResult.query.filter(RadiologyResult.created_at >= (date.today() - timedelta(days=7))).count()
        prev_7 = RadiologyResult.query.filter(
            RadiologyResult.created_at >= (date.today() - timedelta(days=14)),
            RadiologyResult.created_at < (date.today() - timedelta(days=7))
        ).count()
        trend_analysis = 'تصاعدي' if last_7 > prev_7 else 'تنازلي' if last_7 < prev_7 else 'مستقر'
        return {
            'total_reports': total_reports,
            'abnormal_findings': abnormal_findings,
            'abnormal_rate': round(abnormal_rate, 2),
            'critical_reports': critical_reports,
            'trend_analysis': trend_analysis
        }
    except Exception as e:
        logging.error(f"Error getting radiology report analysis: {str(e)}")
        return {}

def get_radiology_workflow_automation():
    """أتمتة سير العمل"""
    try:
        total_requests = RadiologyRequest.query.count()
        done_requests = RadiologyRequest.query.filter(RadiologyRequest.status == OrderState.DONE).count()
        automation_rate = round((done_requests / total_requests) * 100, 2) if total_requests else 0
        automated_tasks = done_requests
        time_saved = round(automation_rate * 1.1, 2)
        efficiency_gain = round(automation_rate * 0.7, 2)
        return {
            'automated_tasks': automated_tasks,
            'automation_rate': automation_rate,
            'time_saved': time_saved,
            'efficiency_gain': efficiency_gain
        }
    except Exception as e:
        logging.error(f"Error getting radiology workflow automation: {str(e)}")
        return {}

def get_radiology_predictive_insights():
    try:
        today = date.today()
        week_start = today - timedelta(days=7)
        month_start = today - timedelta(days=30)
        weekly_requests = RadiologyRequest.query.filter(RadiologyRequest.created_at >= week_start).count()
        monthly_requests = RadiologyRequest.query.filter(RadiologyRequest.created_at >= month_start).count()
        prev_week = RadiologyRequest.query.filter(
            RadiologyRequest.created_at >= today - timedelta(days=14),
            RadiologyRequest.created_at < week_start
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

def calculate_radiology_efficiency(completion_rate, pending_requests):
    """حساب كفاءة الأشعة"""
    try:
        base_score = completion_rate
        penalty = min(pending_requests * 2.5, 25)  # خصم لكل طلب معلق
        return max(base_score - penalty, 0)
    except:
        return 0

def calculate_imaging_efficiency(avg_time, total_requests):
    """حساب كفاءة التصوير"""
    try:
        if avg_time <= 1.5:  # ساعة ونصف أو أقل
            return 95
        elif avg_time <= 3:  # 3 ساعات أو أقل
            return 85
        elif avg_time <= 4.5:  # 4.5 ساعات أو أقل
            return 75
        else:
            return 60
    except:
        return 0

def generate_imaging_optimization_suggestions(avg_time):
    """توليد اقتراحات تحسين التصوير"""
    suggestions = []
    
    if avg_time > 3:
        suggestions.append("تحسين تدفق المرضى")
    if avg_time > 4:
        suggestions.append("إضافة معدات تصوير جديدة")
    if avg_time > 5:
        suggestions.append("زيادة عدد الفنيين")
    
    return suggestions

# ═══════════════════════════════════════
# SUBMODULE IMPORTS
# ═══════════════════════════════════════

from . import dashboard
from . import worklist
from . import requests
from . import reports
from . import images
from . import quality
from . import templates
from . import fhir