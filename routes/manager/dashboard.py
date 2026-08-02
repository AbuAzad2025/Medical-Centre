"""dashboard routes - extracted from monolithic manager.py"""

import logging

from flask import flash, render_template
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_required

from routes.manager import manager_bp
from utils.decorators import role_required


@manager_bp.route('/dashboard')
@login_required
@role_required('manager', 'admin', 'super_admin')
def dashboard() -> ResponseReturnValue:
    """لوحة تحكم المدير — Command Center"""
    try:
        from app.shared.dashboard_service import render_command_center

        return render_command_center(current_user, role='manager')
    except Exception as e:
        logging.exception(f'Error in manager dashboard: {e!s}')
        flash('حدث خطأ في تحميل لوحة التحكم', 'error')
        return render_template('manager/dashboard.html', error=str(e))
