"""departments routes - extracted from monolithic manager.py"""

from routes.manager import manager_bp

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from utils.decorators import manager_or_admin_only, can_approve_force_payment, prevent_self_approval, role_required, role_required_json
from models.patient import Patient
from models.visit import Visit
from models.user import User, StaffWorkSchedule, StaffAbsence
from models.department import Department
from models.payment import Payment
from models.invoice import Invoice
from models.appointment import Appointment
from models.lab_request import LabRequest
from models.radiology_request import RadiologyRequest
from services.gatekeeper_service import GatekeeperService
from services.manager_service import manager_service
from app_factory import db
from sqlalchemy import func
from decimal import Decimal, ROUND_HALF_UP
import logging
from datetime import datetime, date, timedelta, timezone


# =============================================
# DEPARTMENTS ROUTES
# =============================================

@manager_bp.route('/departments')
@login_required
def departments():
    """إدارة الأقسام"""
    if current_user.role not in ['manager', 'admin']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        departments = Department.query.all()
        return render_template('manager/departments.html', departments=departments)
    except Exception as e:
        logging.error(f"Error loading departments: {str(e)}")
        flash('حدث خطأ في تحميل الأقسام', 'error')
        return redirect(url_for('manager.dashboard'))

# ==================== موافقات الدفع القسري (الأسبوع الثاني) ====================
