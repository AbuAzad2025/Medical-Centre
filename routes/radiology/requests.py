"""requests routes - extracted from monolithic radiology.py"""

from routes.radiology import radiology_bp

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for, send_file, current_app
from flask_login import login_required, current_user
from utils.decorators import role_required
from models.patient import Patient
from models.visit import Visit
from models.user import User
from models.radiology_request import RadiologyRequest
from models.radiology_result import RadiologyResult
from models.file_management import FileUpload
from models.system_config import SystemConfig
from services.radiology_service import radiology_service
from app_factory import db
import logging, json, os, base64, secrets
from datetime import datetime, date, timezone, timedelta
from io import BytesIO


# =============================================
# REQUESTS ROUTES
# =============================================

@radiology_bp.route('/requests')
@login_required
@role_required('radiology', 'manager')
def requests():
    """طلبات الأشعة"""
    
    
    return render_template('radiology/radiology_requests.html')

@radiology_bp.route('/tests')
@login_required
@role_required('radiology', 'manager')
def tests():
    """فحوصات الأشعة"""
    
    
    return render_template('radiology/add_scan.html')

@radiology_bp.route('/tests/add', methods=['POST'])
@login_required
@role_required('radiology', 'manager')
def add_scan_post():
    """إضافة فحص أشعة (نقطة إرسال الفورم)"""
    
    try:
        flash('تم استلام بيانات الفحص بنجاح', 'success')
        return redirect(url_for('radiology.tests'))
    except Exception as e:
        logging.error(f"Error adding radiology scan: {str(e)}")
        flash('حدث خطأ أثناء إضافة الفحص', 'error')
        return redirect(url_for('radiology.dashboard'))

@radiology_bp.route('/results')
@login_required
def results():
    """نتائج الأشعة"""
    if current_user.role not in ['radiology', 'manager']:
        flash('ليس لديك صلاحية للوصول إلى هذه الصفحة', 'error')
        return redirect(url_for('main.dashboard'))
    
    try:
        from models.radiology_request import RadiologyRequest
        from models.visit import Visit
        
        from services.access_control_service import AccessControlService
        dept_ids = AccessControlService.get_accessible_department_ids(current_user)
        query = RadiologyRequest.query.filter_by(status='DONE')
        if dept_ids is not None and dept_ids:
            query = query.join(Visit, Visit.id == RadiologyRequest.visit_id).filter(Visit.department_id.in_(dept_ids))
        results = query.order_by(RadiologyRequest.created_at.desc()).all()
        
        return render_template('radiology/results.html', results=results)
    except Exception as e:
        logging.error(f"Error loading radiology results: {str(e)}")
        flash('حدث خطأ في تحميل نتائج الأشعة', 'error')
        return redirect(url_for('radiology.dashboard'))
