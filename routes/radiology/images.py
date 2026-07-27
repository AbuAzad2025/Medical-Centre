"""images routes - extracted from monolithic radiology.py"""

from routes.radiology import radiology_bp

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for, send_file, current_app, g
from flask_login import login_required, current_user
from utils.decorators import role_required
from models.patient import Patient
from models.visit import Visit
from models.user import User
from models.radiology_request import RadiologyRequest
from models.radiology_result import RadiologyResult
from models.file_management import FileUpload
from models.system_config import SystemConfig
from app.extensions import db
from utils.db_safety import safe_commit, safe_rollback
import logging, json, os, base64, secrets
from datetime import datetime, date, timezone, timedelta
from io import BytesIO
from sqlalchemy import select


# =============================================
# IMAGES ROUTES
# =============================================

@radiology_bp.route('/images')
@login_required
@role_required('radiology', 'manager')
def images():
    """صور الأشعة — تُحوِّل لقائمة عمل الأشعة (لا قالب تفاصيل بلا بيانات)."""
    return redirect(url_for('radiology.worklist'))

@radiology_bp.route('/files/<int:file_id>')
@login_required
@role_required('radiology', 'doctor', 'admin', 'manager', 'super_admin')
def download_file(file_id):
    try:
        f = db.session.execute(select(FileUpload).filter(FileUpload.id == file_id, FileUpload.tenant_id == g.tenant_id)).scalars().first()
        if not f:
            flash('الملف غير موجود', 'error')
            return redirect(url_for('radiology.worklist'))
        if f.is_expired():
            flash('انتهت صلاحية الملف', 'error')
            return redirect(url_for('radiology.worklist'))
        if not os.path.exists(f.file_path):
            flash('الملف غير موجود على القرص', 'error')
            return redirect(url_for('radiology.worklist'))
        try:
            f.last_accessed = datetime.now(timezone.utc)
            safe_commit(db.session, error_message="database commit failed", reraise=True)
        except Exception as e:
            safe_rollback(db.session, error_message="database rollback")
        return send_file(f.file_path, as_attachment=True, download_name=f.original_filename)
    except Exception as e:
        logging.error(f"Error downloading radiology file {file_id}: {str(e)}")
        flash('حدث خطأ في تحميل الملف', 'error')
        return redirect(url_for('radiology.worklist'))
