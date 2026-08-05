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
        core_queries.get_basic_dashboard_stats()
        rstats = radiology_service.get_dashboard_stats()
        rstats['today_requests']
        rstats['pending']
        rstats['completed_today']
        db.session.execute(
            select(func.count())
            .select_from(RadiologyRequest)
            .filter(RadiologyRequest.status == OrderState.REQUESTED)
        ).scalar()
        db.session.execute(
            select(func.count())
            .select_from(RadiologyRequest)
            .filter(RadiologyRequest.status == OrderState.IN_PROGRESS)
        ).scalar()
        db.session.execute(
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

        get_radiology_smart_analytics()
        get_radiology_imaging_optimization()
        get_radiology_quality_assurance()
        get_radiology_equipment_status()
        get_radiology_report_analysis()
        get_radiology_workflow_automation()
        get_radiology_predictive_insights()
        (
            db.session.execute(
                select(RadiologyRequest).order_by(RadiologyRequest.created_at.desc()).limit(10)
            )
            .scalars()
            .all()
        )
        from app.shared.dashboard_service import render_command_center

        return render_command_center(current_user)

    except Exception as e:
        logging.exception(f'Error in radiology dashboard: {e!s}')
        flash('حدث خطأ في تحميل لوحة التحكم', 'error')
        return redirect(url_for('main.dashboard'))
