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
        core_queries.get_basic_dashboard_stats()
        lab_stats = lab_service.get_dashboard_stats()
        lab_stats['today_requests']
        lab_stats['pending_requests']
        lab_stats['completed_today']
        db.session.execute(select(func.count()).select_from(LabRequest)).scalar()
        db.session.execute(
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
        db.session.execute(
            select(func.count())
            .select_from(LabRequest)
            .filter(LabRequest.status == OrderState.DONE)
        ).scalar()
        db.session.execute(
            select(func.count())
            .select_from(LabRequest)
            .filter(LabRequest.status == OrderState.REQUESTED)
        ).scalar()
        db.session.execute(
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

        get_lab_smart_analytics()
        get_lab_test_optimization()
        get_lab_quality_control()
        get_lab_equipment_monitoring()
        get_lab_result_analysis()
        get_lab_workflow_automation()
        get_lab_predictive_insights()
        from app.shared.dashboard_service import render_command_center

        return render_command_center(current_user)

    except Exception as e:
        logging.exception(f'Error in lab dashboard: {e!s}')
        flash('حدث خطأ في تحميل لوحة التحكم', 'error')
        return redirect(url_for('main.dashboard'))
