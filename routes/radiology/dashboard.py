"""dashboard routes - extracted from monolithic radiology.py"""

import logging
from datetime import date

# Imports
from flask import (
    flash,
    redirect,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import func, select

from app.extensions import db
from app.shared.enums import OrderState
from models.radiology_request import RadiologyRequest
from routes.radiology import radiology_bp
from services.core_queries import core_queries
from services.radiology_service import radiology_service
from utils.decorators import role_required

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
        today_requests = rstats['today_requests']
        pending_requests = rstats['pending']
        completed_today = rstats['completed_today']
        requested_count = db.session.execute(
            select(func.count())
            .select_from(RadiologyRequest)
            .filter(RadiologyRequest.status == OrderState.REQUESTED)
        ).scalar()
        in_progress_count = db.session.execute(
            select(func.count())
            .select_from(RadiologyRequest)
            .filter(RadiologyRequest.status == OrderState.IN_PROGRESS)
        ).scalar()
        done_today_count = db.session.execute(
            select(func.count())
            .select_from(RadiologyRequest)
            .filter(
                RadiologyRequest.status == OrderState.DONE,
                db.func.date(RadiologyRequest.updated_at) == date.today(),
            )
        ).scalar()
        # Imported here to avoid circular import during blueprint registration.
        from routes.radiology import (
            get_radiology_equipment_status,
            get_radiology_imaging_optimization,
            get_radiology_predictive_insights,
            get_radiology_quality_assurance,
            get_radiology_report_analysis,
            get_radiology_smart_analytics,
            get_radiology_workflow_automation,
        )

        smart_analytics = get_radiology_smart_analytics()
        imaging_optimization = get_radiology_imaging_optimization()
        quality_assurance = get_radiology_quality_assurance()
        equipment_status = get_radiology_equipment_status()
        report_analysis = get_radiology_report_analysis()
        workflow_automation = get_radiology_workflow_automation()
        predictive_insights = get_radiology_predictive_insights()
        recent_requests = (
            db.session.execute(
                select(RadiologyRequest).order_by(RadiologyRequest.created_at.desc()).limit(10)
            )
            .scalars()
            .all()
        )
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
            'predictive_insights': predictive_insights,
        }
        from app.shared.dashboard_service import render_command_center

        return render_command_center(current_user)

    except Exception as e:
        logging.exception(f'Error in radiology dashboard: {e!s}')
        flash('حدث خطأ في تحميل لوحة التحكم', 'error')
        return redirect(url_for('main.dashboard'))
