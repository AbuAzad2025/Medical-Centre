"""images routes - extracted from monolithic radiology.py"""

import logging
import os
from datetime import UTC, datetime

# Imports
from flask import (
    flash,
    g,
    redirect,
    send_file,
    url_for,
)
from flask_login import login_required
from sqlalchemy import select

from app.extensions import db
from models.file_management import FileUpload
from routes.radiology import radiology_bp
from utils.db_safety import safe_commit, safe_rollback
from utils.decorators import role_required

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
        f = (
            db.session.execute(
                select(FileUpload).filter(
                    FileUpload.id == file_id, FileUpload.tenant_id == g.tenant_id
                )
            )
            .scalars()
            .first()
        )
        if not f:
            flash('الملف غير موجود', 'error')
            return redirect(url_for('radiology.worklist'))
        if f.is_expired():
            flash('انتهت صلاحية الملف', 'error')
            return redirect(url_for('radiology.worklist'))

        # For S3/MinIO, redirect to pre-signed URL
        if f.storage_backend in ('s3', 'minio'):
            from services.file_service import FileService

            presigned_url = FileService.generate_presigned_url(f)
            if presigned_url:
                try:
                    f.last_accessed = datetime.now(UTC)
                    safe_commit(db.session, error_message='database commit failed', reraise=True)
                except Exception:
                    safe_rollback(db.session, error_message='database rollback')
                return redirect(presigned_url)
            flash('تعذر إنشاء رابط التحميل', 'error')
            return redirect(url_for('radiology.worklist'))

        # Local storage fallback
        if not f.file_path or not os.path.exists(f.file_path):
            flash('الملف غير موجود على القرص', 'error')
            return redirect(url_for('radiology.worklist'))
        try:
            f.last_accessed = datetime.now(UTC)
            safe_commit(db.session, error_message='database commit failed', reraise=True)
        except Exception:
            safe_rollback(db.session, error_message='database rollback')
        return send_file(f.file_path, as_attachment=True, download_name=f.original_filename)
    except Exception:
        logging.exception('Error downloading radiology file {file_id}: %s')
        flash('حدث خطأ في تحميل الملف', 'error')
        return redirect(url_for('radiology.worklist'))
