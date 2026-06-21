"""worklist routes - extracted from monolithic lab.py"""

from routes.lab import lab_bp

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for, send_file, make_response
from flask_login import login_required, current_user
from utils.decorators import role_required
from models.patient import Patient
from models.visit import Visit
from models.user import User
from models.lab_request import LabRequest
from models.lab_request import LabResult
from models.lab_quality import LabQualityControlEntry
from models.lab_reagent import LabReagent
from models.audit_trail import AuditTrail
from services.lab_service import lab_service
from app_factory import db
import logging, json, base64
from datetime import datetime, date, timezone, timedelta
from io import BytesIO


# =============================================
# WORKLIST ROUTES
# =============================================

@lab_bp.route('/requests')
@login_required
@role_required('lab', 'manager')
def requests():
    """طلبات المختبر"""
    
    
    return redirect(url_for('lab.worklist'))

@lab_bp.route('/results')
@login_required
@role_required('lab', 'manager')
def results():
    """نتائج المختبر"""
    
    
    return redirect(url_for('lab.worklist', status='DONE_TODAY'))

@lab_bp.route('/tests')
@login_required
@role_required('lab', 'admin', 'manager')
def tests():
    """الفحوصات"""
    
    
    return redirect(url_for('lab.requests'))

@lab_bp.route('/worklist')
@login_required
@role_required('lab', 'technician', 'admin', 'manager')
def worklist():
    try:
        status = (request.args.get('status') or 'REQUESTED').strip().upper()
        reqs = lab_service.get_worklist(status=status)
        counts = lab_service.get_request_counts()
        return render_template('lab/process.html',
                               requests=reqs,
                               status=status,
                               counts=counts)
    except Exception as e:
        logging.error(f"Error loading lab worklist: {str(e)}")
        flash('حدث خطأ في تحميل قائمة العمل', 'error')
        return redirect(url_for('lab.dashboard'))

def _process_lab_results_form(lab_request, form):
    """معالجة نتائج المختبر من بيانات النموذج"""
    from services.lab_service import lab_service
    result_ids = form.getlist('result_id[]')
    test_codes = form.getlist('test_code[]')
    test_names = form.getlist('test_name[]')
    values = form.getlist('value[]')
    units = form.getlist('unit[]')
    ranges = form.getlist('reference_range[]')
    critical_flags = form.getlist('is_critical[]')
    statuses = form.getlist('status[]')
    notes_list = form.getlist('notes[]')

    any_change = False
    max_len = max(len(result_ids), len(test_codes), len(test_names), len(values),
                  len(units), len(ranges), len(critical_flags), len(statuses), len(notes_list), 0)
    for i in range(max_len):
        rid_raw = result_ids[i] if i < len(result_ids) else ''
        test_code = (test_codes[i] if i < len(test_codes) else '').strip()
        test_name = (test_names[i] if i < len(test_names) else '').strip()
        value = (values[i] if i < len(values) else '').strip()
        unit = (units[i] if i < len(units) else '').strip() or None
        reference_range = (ranges[i] if i < len(ranges) else '').strip() or None
        is_critical = str((critical_flags[i] if i < len(critical_flags) else '').strip()) in {'1', 'true', 'True', 'yes', 'on'}
        status_val = (statuses[i] if i < len(statuses) else '').strip().upper() or 'PENDING'
        notes = (notes_list[i] if i < len(notes_list) else '').strip() or None

        if not (test_code or test_name or value or unit or reference_range or notes):
            continue

        if not unit or not reference_range:
            catalog_entry = lab_service.lookup_catalog_by_code(
                test_code, getattr(current_user, 'tenant_id', None)
            )
            if catalog_entry:
                if not unit:
                    unit = catalog_entry.unit or None
                if not reference_range:
                    reference_range = catalog_entry.default_reference_range or None

        if rid_raw and str(rid_raw).isdigit():
            res = db.session.get(LabResult, int(rid_raw))
            if not res or res.request_id != lab_request.id:
                continue
            res.performed_by = current_user.id
            if test_code:
                res.test_code = test_code
            if test_name:
                res.test_name = test_name
            res.value = value or None
            res.unit = unit
            res.reference_range = reference_range
            if status_val in {'PENDING', 'READY', 'VALIDATED'}:
                res.status = status_val
            res.notes = notes
            res.is_critical = is_critical
            any_change = True
        else:
            if not (test_code and test_name):
                continue
            res = LabResult(
                request_id=lab_request.id, patient_id=lab_request.patient_id,
                performed_by=current_user.id,
                test_code=test_code, test_name=test_name, value=value or None,
                unit=unit, reference_range=reference_range,
                status=status_val if status_val in {'PENDING', 'READY', 'VALIDATED'} else 'PENDING',
                notes=notes, is_critical=is_critical
            )
            db.session.add(res)
            any_change = True
    return any_change


def _notify_lab_results_ready(lab_request):
    """إرسال إشعار للطبيب باستكمال نتائج المختبر"""
    try:
        from services.notification_service import NotificationService
        doctor_id = lab_request.requester.id if lab_request.requester else None
        has_critical = False
        try:
            for res in lab_request.results:
                if res.is_critical and (res.value or '').strip():
                    has_critical = True
                    break
        except Exception:
            has_critical = False
        if doctor_id:
            NotificationService.send_notification(
                recipient_id=doctor_id,
                title='نتيجة فحص مختبر جاهزة',
                message=f'تم اعتماد نتيجة فحص المختبر لطلب #{lab_request.id}' + (' (نتائج حرجة)' if has_critical else ''),
                notification_type='error' if has_critical else 'info',
                is_urgent=bool(has_critical)
            )
        if has_critical:
            NotificationService.send_notification(
                recipient_role='reception',
                title='نتائج مختبر حرجة',
                message=f'يوجد نتائج مختبر حرجة لطلب #{lab_request.id} للمريض #{lab_request.patient_id}',
                notification_type='error', is_urgent=True
            )
    except Exception:

        logging.warning(f"Error in {__name__}: {e}")
@lab_bp.route('/worklist/request/<int:request_id>', methods=['GET', 'POST'])
@login_required
@role_required('lab', 'technician', 'admin', 'manager', 'super_admin')
def worklist_request(request_id):
    try:
        lab_request = db.session.get(LabRequest, request_id)
        if not lab_request:
            flash('الطلب غير موجود', 'error')
            return redirect(url_for('lab.worklist'))

        if request.method == 'POST':
            action = (request.form.get('action') or 'save').strip().lower()
            if action in {'receive', 'analyze', 'review', 'approve', 'start'}:
                status_map = {
                    'receive': 'RECEIVED',
                    'analyze': 'ANALYZING',
                    'review': 'REVIEWED',
                    'approve': 'APPROVED',
                    'start': 'IN_PROGRESS'
                }
                new_status = status_map.get(action)
                if new_status and lab_request.status != new_status:
                    lab_request.status = new_status
                    lab_request.updated_at = datetime.now(timezone.utc)
                    _log_lab_workflow(lab_request.id, new_status, action)
            any_change = _process_lab_results_form(lab_request, request.form)

            if action == 'finalize':
                for res in lab_request.results:
                    if (res.value or '').strip():
                        res.status = 'VALIDATED'
                        res.performed_by = current_user.id
                lab_request.status = 'DONE'
                lab_request.completed_at = datetime.now(timezone.utc)
                lab_request.updated_at = datetime.now(timezone.utc)
                _log_lab_workflow(lab_request.id, 'DONE', 'finalize')
                any_change = True

                _notify_lab_results_ready(lab_request)

            if any_change:
                try:
                    db.session.add(AuditTrail(
                        entity_type='lab_request',
                        entity_id=lab_request.id,
                        action='update',
                        user_id=current_user.id,
                        user_ip=request.remote_addr,
                        user_agent=request.headers.get('User-Agent'),
                        description='تحديث نتائج المختبر'
                    ))
                except Exception:

                    logging.warning(f"Error in {__name__}: {e}")
            db.session.commit()
            flash('تم حفظ نتائج المختبر', 'success')
            return redirect(url_for('lab.worklist_request', request_id=lab_request.id))

        return render_template('lab/process.html', lab_request=lab_request)
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error in lab worklist request: {str(e)}")
        flash('حدث خطأ في إدارة الطلب', 'error')
        return redirect(url_for('lab.worklist'))

@lab_bp.route('/worklist/claim/<int:request_id>', methods=['POST'])
@login_required
@role_required('lab', 'technician', 'admin', 'manager', 'super_admin')
def worklist_claim(request_id):
    try:
        req = db.session.get(LabRequest, request_id)
        if not req or req.status not in ('REQUESTED',):
            return jsonify({'success': False, 'message': 'الطلب غير صالح'}), 400
        req.status = 'RECEIVED'
        req.updated_at = datetime.now(timezone.utc)
        _log_lab_workflow(req.id, 'RECEIVED', 'claim')
        db.session.commit()
        return jsonify({'success': True, 'message': 'تم استلام الطلب'}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error claiming lab request: {str(e)}")
        return jsonify({'success': False, 'message': 'حدث خطأ'}), 500

@lab_bp.route('/worklist/complete/<int:request_id>', methods=['POST'])
@login_required
@role_required('lab', 'technician', 'admin', 'manager', 'super_admin')
def worklist_complete(request_id):
    try:
        req = db.session.get(LabRequest, request_id)
        if not req:
            return jsonify({'success': False, 'message': 'الطلب غير موجود'}), 404
        # إنشاء نتيجة مبسطة إذا لم تُرفق
        result_payload = request.get_json() or {}
        if result_payload:
            res = LabResult(
                request_id=req.id,
                patient_id=req.patient_id,
                performed_by=current_user.id,
                test_code=result_payload.get('test_code') or 'GEN',
                test_name=result_payload.get('test_name') or 'Generic Test',
                value=result_payload.get('value'),
                unit=result_payload.get('unit'),
                reference_range=result_payload.get('reference_range'),
                status='VALIDATED',
                notes=result_payload.get('notes'),
                is_critical=bool(result_payload.get('is_critical') or False)
            )
            db.session.add(res)
        req.status = 'DONE'
        req.completed_at = datetime.now(timezone.utc)
        req.updated_at = datetime.now(timezone.utc)
        _log_lab_workflow(req.id, 'DONE', 'complete')
        db.session.commit()

        try:
            from services.notification_service import NotificationService
            # إشعار للطبيب الطالب إن وُجد
            doctor_id = req.requester.id if req.requester else None
            if doctor_id:
                NotificationService.send_notification(
                    recipient_id=doctor_id,
                    title='نتيجة فحص مختبر جاهزة',
                    message=f'تم اعتماد نتيجة فحص المختبر لطلب #{req.id}',
                    notification_type='info'
                )
        except Exception:

            logging.warning(f"Error in {__name__}: {e}")
        return jsonify({'success': True, 'message': 'تم إكمال الطلب'}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error completing lab request: {str(e)}")
        return jsonify({'success': False, 'message': 'حدث خطأ'}), 500
