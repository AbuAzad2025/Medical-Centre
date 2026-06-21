"""dashboard routes - extracted from monolithic radiology.py"""

from routes.radiology import radiology_bp

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for, send_file, current_app
from flask_login import login_required, current_user
from utils.decorators import role_required
from models.patient import Patient
from models.visit import Visit
from models.user import User
from models.radiology_request import RadiologyRequest
from models.radiology_result import RadiologyResult
from models.file_management import FileUpload
from models.system_config import SystemConfig
from services.core_queries import core_queries
from services.radiology_service import radiology_service
from app_factory import db
import logging, json, os, base64, secrets
from datetime import datetime, date, timezone, timedelta
from io import BytesIO


# =============================================
# DASHBOARD ROUTES
# =============================================

@radiology_bp.route('/')
@login_required
def index():
    return redirect(url_for('radiology.dashboard'))

@radiology_bp.route('/dashboard')
@login_required
@role_required('radiology', 'manager')
def dashboard():
    """لوحة تحكم الأشعة الذكية"""
    
    
    try:
        base = core_queries.get_basic_dashboard_stats()
        rstats = radiology_service.get_dashboard_stats()
        today_requests = rstats["today_requests"]
        pending_requests = rstats["pending"]
        completed_today = rstats["completed_today"]
        requested_count = RadiologyRequest.query.filter(
            RadiologyRequest.status == OrderState.REQUESTED
        ).count()
        in_progress_count = RadiologyRequest.query.filter(
            RadiologyRequest.status == OrderState.IN_PROGRESS
        ).count()
        done_today_count = RadiologyRequest.query.filter(
            RadiologyRequest.status == OrderState.DONE,
            db.func.date(RadiologyRequest.updated_at) == date.today()
        ).count()
        smart_analytics = get_radiology_smart_analytics()
        imaging_optimization = get_radiology_imaging_optimization()
        quality_assurance = get_radiology_quality_assurance()
        equipment_status = get_radiology_equipment_status()
        report_analysis = get_radiology_report_analysis()
        workflow_automation = get_radiology_workflow_automation()
        predictive_insights = get_radiology_predictive_insights()
        recent_requests = RadiologyRequest.query.order_by(RadiologyRequest.created_at.desc()).limit(10).all()
        stats = {
            'today_requests': today_requests,
            'pending_requests': pending_requests,
            'completed_today': completed_today,
            'requested_count': requested_count,
            'in_progress_count': in_progress_count,
            'done_today_count': done_today_count,
            'smart_analytics': smart_analytics,
            'imaging_optimization': imaging_optimization,
            'quality_assurance': quality_assurance,
            'equipment_status': equipment_status,
            'report_analysis': report_analysis,
            'workflow_automation': workflow_automation,
            'predictive_insights': predictive_insights
        }
        return render_template('radiology/dashboard_new.html', stats=stats, recent_requests=recent_requests)
    
    except Exception as e:
        logging.error(f"Error in radiology dashboard: {str(e)}")
        flash('حدث خطأ في تحميل لوحة التحكم', 'error')
        return redirect(url_for('main.dashboard'))
