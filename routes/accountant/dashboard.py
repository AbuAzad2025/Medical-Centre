"""Dashboard routes — accountant command center (production).

Delegates to the shared Command Center which provides role-appropriate,
tenant-isolated data via dashboard_service._load_role_data. No business
logic is duplicated here; all metrics are loaded centrally to avoid
tazahum and ensure a single source of truth.
"""

from __future__ import annotations

import logging

from flask import flash, redirect, url_for
from flask_login import current_user, login_required

from routes.accountant import accountant_bp
from utils.decorators import role_required

logger = logging.getLogger(__name__)


@accountant_bp.route('/')
@login_required
@role_required('accountant', 'admin', 'manager')
def index() -> str:
    """توجيه تلقائي إلى لوحة التحكم."""
    return redirect(url_for('accountant.dashboard'))


@accountant_bp.route('/dashboard')
@login_required
@role_required('accountant', 'admin', 'manager')
def dashboard() -> str:
    """لوحة تحكم المحاسب — Command Center tenant-isolated."""
    try:
        from app.shared.dashboard_service import render_command_center

        return render_command_center(current_user)
    except Exception:  # pragma: no cover — defensive
        logging.exception('Error in accountant dashboard')
        flash('حدث خطأ في تحميل لوحة التحكم', 'error')
        try:
            from app.shared.dashboard_service import render_command_center

            return render_command_center(current_user)
        except Exception:
            return redirect(url_for('main.dashboard'))
