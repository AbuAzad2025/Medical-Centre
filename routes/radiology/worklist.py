"""worklist routes - extracted from monolithic radiology.py"""

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
from werkzeug.utils import secure_filename


# =============================================
# WORKLIST ROUTES
# =============================================


def _parse_radiology_payload():
    """استخراج البيانات من الطلب (JSON أو form)"""
    if request.is_json:
        payload = request.get_json() or {}
    else:
        payload = dict(request.form) if request.form else {}
    is_critical_raw = payload.get('is_critical')
    if isinstance(is_critical_raw, list):
        is_critical_raw = is_critical_raw[0] if is_critical_raw else None
    is_critical = False
    if isinstance(is_critical_raw, str):
        is_critical = is_critical_raw.strip().lower() in {'1', 'true', 'yes', 'on'}
    elif isinstance(is_critical_raw, (bool, int)):
        is_critical = bool(is_critical_raw)
    return payload, is_critical


def _handle_radiology_file_uploads(files, result, payload):
    """رفع ملفات الصور للنتيجة"""
    if not files:
        return
    upload_root = current_app.config.get('UPLOAD_FOLDER') or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..', 'static', 'uploads')
    target_dir = os.path.join(upload_root, 'radiology', str(result.id))
    os.makedirs(target_dir, exist_ok=True)
    for f in files:
        if not f or not getattr(f, 'filename', None):
            continue
        original_name = f.filename
        safe_name = secure_filename(original_name) or f'file_{secrets.token_hex(4)}'
        _, ext = os.path.splitext(safe_name)
        stored_name = f'{datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")}_{secrets.token_hex(8)}{ext.lower()}'
        file_path = os.path.join(target_dir, stored_name)
        f.save(file_path)
        size = 0
        try:
            size = os.path.getsize(file_path)
        except Exception:
            size = 0
        fu = FileUpload(
            filename=stored_name, original_filename=original_name,
            file_path=file_path, file_size=(size or 1),
            file_type=(getattr(f, 'mimetype', None) or 'application/octet-stream'),
            file_extension=(ext.lower().lstrip('.') or 'bin'),
            description=(payload.get('file_description') if payload else None),
            related_entity_type='radiology_result',
            related_entity_id=result.id,
            uploaded_by=current_user.id
        )
        db.session.add(fu)


def _notify_radiology_complete(req, is_critical):
    """إرسال إشعار للطبيب باستكمال تقرير الأشعة"""
    try:
        from services.notification_service import NotificationService
        doctor_id = req.requester.id if req.requester else None
        if doctor_id:
            NotificationService.send_notification(
                recipient_id=doctor_id,
                title='نتيجة الأشعة جاهزة',
                message=f'تم اعتماد تقرير الأشعة لطلب #{req.id}' + (' (حرج)' if is_critical else ''),
                notification_type=('warning' if is_critical else 'info'),
                is_urgent=is_critical,
            )
            if is_critical:
                NotificationService.send_notification(
                    recipient_role='reception',
                    title='نتيجة أشعة حرجة',
                    message=f'يوجد تقرير أشعة حرج لطلب #{req.id} للمريض #{req.patient_id}',
                    notification_type='warning', is_urgent=True
                )
    except Exception:
        pass


@radiology_bp.route('/worklist')
@login_required
@role_required('radiology', 'technician', 'admin', 'manager')
def worklist():
    try:
        counts = radiology_service.get_request_counts()
        status = request.args.get('status') or 'REQUESTED'
        requests_list = radiology_service.get_worklist(status=status)
        visits_by_id = radiology_service.build_visit_map(requests_list)
        return render_template('radiology/process.html',
                               requests=requests_list,
                               status=status,
                               counts=counts,
                               visits_by_id=visits_by_id)
    except Exception as e:
        logging.error(f"Error loading radiology worklist: {str(e)}")
        flash('حدث خطأ في تحميل قائمة العمل', 'error')
        return redirect(url_for('radiology.dashboard'))

@radiology_bp.route('/worklist/request/<int:request_id>', methods=['GET'])
@login_required
@role_required('radiology', 'technician', 'admin', 'manager', 'super_admin')
def worklist_request(request_id):
    try:
        rad_request = radiology_service.get_request_by_id(request_id)
        if not rad_request:
            flash('الطلب غير موجود', 'error')
            return redirect(url_for('radiology.worklist'))

        existing_result = radiology_service.get_results_for_request(request_id)
        uploads = []
        if existing_result:
            uploads = radiology_service.get_uploads_for_result(existing_result.id)

        visit_summary = None
        if getattr(rad_request, 'visit_id', None):
            from models.visit import Visit
            visit_summary = Visit.query.get(rad_request.visit_id)
        return render_template('radiology/process.html', radiology_request=rad_request, radiology_result=existing_result, uploads=uploads, visit_summary=visit_summary)
    except Exception as e:
        logging.error(f"Error loading radiology request {request_id}: {str(e)}")
        flash('حدث خطأ في تحميل الطلب', 'error')
        return redirect(url_for('radiology.worklist'))

@radiology_bp.route('/worklist/claim/<int:request_id>', methods=['POST'])
@login_required
@role_required('radiology', 'technician', 'admin', 'manager', 'super_admin')
def worklist_claim(request_id):
    try:
        success = radiology_service.claim_request(request_id, current_user.id)
        if not success:
            if request.accept_mimetypes.best == 'application/json':
                return jsonify({'success': False, 'message': 'الطلب غير صالح'}), 400
            flash('الطلب غير صالح', 'error')
            return redirect(url_for('radiology.worklist'))
        radiology_service.log_action(f"Claimed radiology request #{request_id}", f"User {current_user.id}", current_user.id)
        if request.accept_mimetypes.best == 'application/json':
            return jsonify({'success': True, 'message': 'تم استلام الطلب'}), 200
        flash('تم استلام الطلب', 'success')
        return redirect(url_for('radiology.worklist', status='IN_PROGRESS'))
    except Exception as e:
        logging.error(f"Error claiming radiology request: {str(e)}")
        if request.accept_mimetypes.best == 'application/json':
            return jsonify({'success': False, 'message': 'حدث خطأ'}), 500
        flash('حدث خطأ', 'error')
        return redirect(url_for('radiology.worklist'))

@radiology_bp.route('/worklist/complete/<int:request_id>', methods=['POST'])
@login_required
@role_required('radiology', 'technician', 'admin', 'manager', 'super_admin')
def worklist_complete(request_id):
    try:
        req = db.session.get(RadiologyRequest, request_id)
        if not req:
            if request.accept_mimetypes.best == 'application/json':
                return jsonify({'success': False, 'message': 'الطلب غير موجود'}), 404
            flash('الطلب غير موجود', 'error')
            return redirect(url_for('radiology.worklist'))

        action = (request.form.get('action') if request.form else None) or None
        payload, is_critical = _parse_radiology_payload()

        existing_result = req.results[0] if req.results else None
        if existing_result:
            res = existing_result
            was_reviewed = bool(getattr(res, 'reviewed_at', None))
            before = {
                'study_uid': res.study_uid,
                'findings': res.findings,
                'impression': res.impression,
                'notes': res.notes,
                'is_critical': bool(res.is_critical),
            }
            res.performed_by = current_user.id
            res.study_uid = payload.get('study_uid') or payload.get('studyUID') or res.study_uid
            res.pacs_url = payload.get('pacs_url') or payload.get('pacsURL') or res.pacs_url
            res.findings = payload.get('findings') or res.findings
            res.impression = payload.get('impression') or payload.get('results') or res.impression
            res.notes = payload.get('notes') or payload.get('recommendations') or res.notes
            if action == 'second_review':
                res.reviewed_by = current_user.id
                res.reviewed_at = datetime.now(timezone.utc)
            res.status = 'VALIDATED' if (action in (None, 'finalize', 'second_review')) else (res.status or 'PENDING')
            res.is_critical = is_critical
            if was_reviewed:
                after = {
                    'study_uid': res.study_uid,
                    'findings': res.findings,
                    'impression': res.impression,
                    'notes': res.notes,
                    'is_critical': bool(res.is_critical),
                }
                if after != before:
                    res.revised_after_review = True
        else:
            res = RadiologyResult(
                request_id=req.id,
                patient_id=req.patient_id,
                performed_by=current_user.id,
                study_uid=payload.get('study_uid') or payload.get('studyUID'),
                pacs_url=payload.get('pacs_url') or payload.get('pacsURL'),
                findings=payload.get('findings'),
                impression=payload.get('impression') or payload.get('results'),
                status='VALIDATED' if (action in (None, 'finalize')) else 'PENDING',
                notes=payload.get('notes') or payload.get('recommendations'),
                is_critical=is_critical
            )
            db.session.add(res)
            db.session.flush()

        if payload.get('body_part'):
            req.body_part = payload.get('body_part')
        if payload.get('description'):
            req.notes = payload.get('description')
        if payload.get('test_name'):
            tn = (payload.get('test_name') or '').lower()
            if 'ct' in tn:
                req.modality = 'CT'
            elif 'mri' in tn:
                req.modality = 'MRI'
            elif 'ultra' in tn:
                req.modality = 'US'
            else:
                req.modality = req.modality or 'XRay'

        _handle_radiology_file_uploads(request.files.getlist('image_upload') if request.files else [], res, payload)

        should_finalize = action in (None, 'finalize')
        if should_finalize:
            req.status = 'DONE'
            _log_radiology_workflow(req.id, 'DONE', 'finalize')
        else:
            if req.status == 'REQUESTED':
                req.status = 'IN_PROGRESS'
                _log_radiology_workflow(req.id, 'IN_PROGRESS', 'start')
        req.updated_at = datetime.now(timezone.utc)
        db.session.commit()

        _notify_radiology_complete(req, bool(is_critical))

        if request.accept_mimetypes.best == 'application/json':
            return jsonify({'success': True, 'message': 'تم إكمال الطلب'}), 200
        flash('تم حفظ تقرير الأشعة', 'success')
        if should_finalize:
            return redirect(url_for('radiology.worklist', status='DONE_TODAY'))
        return redirect(url_for('radiology.worklist_request', request_id=req.id))
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error completing radiology request: {str(e)}")
        if request.accept_mimetypes.best == 'application/json':
            return jsonify({'success': False, 'message': 'حدث خطأ'}), 500
        flash('حدث خطأ', 'error')
        return redirect(url_for('radiology.worklist'))
