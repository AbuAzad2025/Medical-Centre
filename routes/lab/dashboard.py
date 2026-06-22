"""dashboard routes - extracted from monolithic lab.py"""

from routes.lab import lab_bp

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for, send_file, make_response
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
from services.core_queries import core_queries
from services.lab_service import lab_service
from app_factory import db
from app.shared.enums import OrderState
import logging, json, base64
from datetime import datetime, date, timezone, timedelta
from io import BytesIO


# =============================================
# DASHBOARD ROUTES
# =============================================

@lab_bp.route('/')
@login_required
def index():
    return redirect(url_for('lab.dashboard'))

@lab_bp.route('/dashboard')
@login_required
@role_required('lab', 'admin', 'manager')
def dashboard():
    """لوحة تحكم المختبر الذكية"""
    
    
    try:
        base = core_queries.get_basic_dashboard_stats()
        lab_stats = lab_service.get_dashboard_stats()
        today_requests = lab_stats["today_requests"]
        pending_requests = lab_stats["pending_requests"]
        completed_today = lab_stats["completed_today"]
        total_tests = LabRequest.query.count()
        pending_tests = LabRequest.query.filter(
            LabRequest.status.in_([OrderState.REQUESTED, OrderState.RECEIVED, OrderState.ANALYZING, OrderState.REVIEWED, OrderState.APPROVED, OrderState.IN_PROGRESS])
        ).count()
        completed_tests = LabRequest.query.filter(
            LabRequest.status == OrderState.DONE
        ).count()
        requested_count = LabRequest.query.filter(
            LabRequest.status == OrderState.REQUESTED
        ).count()
        in_progress_count = LabRequest.query.filter(
            LabRequest.status.in_([OrderState.RECEIVED, OrderState.ANALYZING, OrderState.REVIEWED, OrderState.APPROVED, OrderState.IN_PROGRESS])
        ).count()
        # Imported here to avoid circular import during blueprint registration.
        from routes.lab import (
            get_lab_smart_analytics,
            get_lab_test_optimization,
            get_lab_quality_control,
            get_lab_equipment_monitoring,
            get_lab_result_analysis,
            get_lab_workflow_automation,
            get_lab_predictive_insights,
        )
        smart_analytics = get_lab_smart_analytics()
        test_optimization = get_lab_test_optimization()
        quality_control = get_lab_quality_control()
        equipment_monitoring = get_lab_equipment_monitoring()
        result_analysis = get_lab_result_analysis()
        workflow_automation = get_lab_workflow_automation()
        predictive_insights = get_lab_predictive_insights()
        stats = {
            'today_requests': today_requests,
            'pending_requests': pending_requests,
            'completed_today': completed_today,
            'requested_count': requested_count,
            'in_progress_count': in_progress_count,
            'total_tests': total_tests,
            'pending_tests': pending_tests,
            'completed_tests': completed_tests,
            'smart_analytics': smart_analytics,
            'test_optimization': test_optimization,
            'quality_control': quality_control,
            'equipment_monitoring': equipment_monitoring,
            'result_analysis': result_analysis,
            'workflow_automation': workflow_automation,
            'predictive_insights': predictive_insights
        }
        recent_requests = LabRequest.query.order_by(LabRequest.created_at.desc()).limit(10).all()
        return render_template('lab/dashboard_new.html', stats=stats, recent_requests=recent_requests)
    
    except Exception as e:
        logging.error(f"Error in lab dashboard: {str(e)}")
        flash('حدث خطأ في تحميل لوحة التحكم', 'error')
        return redirect(url_for('main.dashboard'))
