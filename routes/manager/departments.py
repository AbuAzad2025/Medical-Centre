"""departments routes - extracted from monolithic manager.py"""

import logging

# Imports
from flask import flash, redirect, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from models.department import Department
from routes.manager import manager_bp
from utils.decorators import (
    role_required,
)

# =============================================
# DEPARTMENTS ROUTES
# =============================================


@manager_bp.route('/departments')
@login_required
@role_required('manager', 'admin')
def departments():
    """إدارة الأقسام"""
    try:
        departments = (
            db.session.execute(
                select(Department).filter(Department.tenant_id == current_user.tenant_id)
            )
            .scalars()
            .all()
        )
        return render_template('manager/departments.html', departments=departments)
    except Exception:
        logging.exception('Error loading departments: %s')
        flash('حدث خطأ في تحميل الأقسام', 'error')
        return redirect(url_for('manager.dashboard'))


# ==================== موافقات الدفع القسري (الأسبوع الثاني) ====================
