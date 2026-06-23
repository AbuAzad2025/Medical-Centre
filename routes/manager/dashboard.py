"""dashboard routes - extracted from monolithic manager.py"""

from routes.manager import manager_bp

from flask import flash, redirect, url_for
from flask.typing import ResponseReturnValue
from flask_login import login_required, current_user
from utils.decorators import role_required
import logging


@manager_bp.route('/dashboard')
@login_required
@role_required('manager', 'admin', 'super_admin')
def dashboard() -> ResponseReturnValue:
    """لوحة تحكم المدير — Command Center"""
    try:
        from app.shared.dashboard_service import render_command_center
        return render_command_center(current_user, role='manager')
    except Exception as e:
        logging.error(f"Error in manager dashboard: {str(e)}")
        flash('حدث خطأ في تحميل لوحة التحكم', 'error')
        return redirect(url_for('main.dashboard'))
