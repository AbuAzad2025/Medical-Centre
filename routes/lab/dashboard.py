"""dashboard routes - extracted from monolithic lab.py"""

import logging

# Imports
from flask import (
    flash,
    redirect,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import func, select

from app.core.saas.decorators import require_entitlement
from app.extensions import db
from app.shared.enums import OrderState
from models.lab_request import LabRequest
from routes.lab import lab_bp
from services.core_queries import core_queries
from services.lab_service import lab_service
from utils.decorators import role_required

# =============================================
# DASHBOARD ROUTES
# =============================================


@lab_bp.route('/')
@login_required
def index():
    return redirect(url_for('lab.dashboard'))


@lab_bp.route('/dashboard')
@login_required
@require_entitlement('lab_order')
@role_required('lab', 'admin', 'manager')
def dashboard():
    """لوحة تحكم المختبر الذكية"""

    try:
        base = core_queries.get_basic_dashboard_stats()
        lab_stats = lab_service.get_dashboard_stats()
        today_requests = lab_stats['today_requests']
        pending_requests = lab_stats['pending_requests']
        completed_today = lab_stats['completed_today']
        total_tests = db.session.execute(select(func.count()).select_from(LabRequest)).scalar()
        pending_tests = db.session.execute(
            select(func.count())
            .select_from(LabRequest)
            .filter(
                LabRequest.status.in_(
                    [
                        OrderState.REQUESTED,
                        OrderState.RECEIVED,
                        OrderState.ANALYZING,
                        OrderState.REVIEWED,
                        OrderState.APPROVED,
                        OrderState.IN_PROGRESS,
                    ]
                )
            )
        ).scalar()
        completed_tests = db.session.execute(
            select(func.count())
            .select_from(LabRequest)
            .filter(LabRequest.status == OrderState.DONE)
        ).scalar()
        requested_count = db.session.execute(
            select(func.count())
            .select_from(LabRequest)
            .filter(LabRequest.status == OrderState.REQUESTED)
        ).scalar()
        in_progress_count = db.session.execute(
            select(func.count())
            .select_from(LabRequest)
            .filter(
                LabRequest.status.in_(
                    [
                        OrderState.RECEIVED,
                        OrderState.ANALYZING,
                        OrderState.REVIEWED,
                        OrderState.APPROVED,
                        OrderState.IN_PROGRESS,
                    ]
                )
            )
        ).scalar()
        # Imported here to avoid circular import during blueprint registration.
        from routes.lab import (
            get_lab_equipment_monitoring,
            get_lab_predictive_insights,
            get_lab_quality_control,
            get_lab_result_analysis,
            get_lab_smart_analytics,
            get_lab_test_optimization,
            get_lab_workflow_automation,
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
            'predictive_insights': predictive_insights,
        }
        from app.shared.dashboard_service import render_command_center

        return render_command_center(current_user)

    except Exception as e:
        logging.exception(f'Error in lab dashboard: {e!s}')
        flash('حدث خطأ في تحميل لوحة التحكم', 'error')
        return redirect(url_for('main.dashboard'))
