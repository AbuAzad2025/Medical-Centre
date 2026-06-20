"""notes routes - extracted from monolithic doctor.py"""

from routes.doctor import doctor_bp

# Imports
from flask import render_template, request, jsonify, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from utils.decorators import role_required, role_required_json
from models.patient import Patient
from models.visit import Visit
from models.user import User
from models.department import Department
from models.medication import Prescription
from models.lab_request import LabRequest
from models.radiology_request import RadiologyRequest
from models.medical_record import MedicalRecord
from models.appointment import Appointment
from models.follow_up import FollowUpRequest
from models.drug_interaction import DrugInteraction
from models.audit_trail import AuditTrail
from models.system_config import SystemConfig
from app_factory import db
from sqlalchemy import and_, or_, desc, func, case
import logging, json, secrets
from datetime import datetime, date, timedelta, timezone


# =============================================
# NOTES ROUTES
# =============================================

@doctor_bp.route('/notes/<int:visit_id>', methods=['GET', 'POST'])
@login_required
@role_required('doctor', 'admin', 'manager')
def notes(visit_id):
    """كتابة الملاحظات الطبية"""
    
    try:
        visit = db.session.get(Visit, visit_id)
        if not visit or visit.doctor_id != current_user.id:
            flash('الزيارة غير موجودة أو ليس لديك صلاحية', 'error')
            return redirect(url_for('doctor.patient_queue'))
        if visit.status == 'ARCHIVED':
            flash('لا يمكن إضافة ملاحظات بعد أرشفة الزيارة', 'warning')
            return redirect(url_for('doctor.patient_queue'))
        
        note_type = request.args.get('type') or request.form.get('note_type')
        prefill_notes = None
        if note_type == 'lab':
            prefill_notes = "مذكرة تحاليل:\nنوع الفحص:\nسبب الفحص:\nتعليمات إضافية:"
        elif note_type == 'radiology':
            prefill_notes = "مذكرة تصوير:\nنوع التصوير:\nمنطقة التصوير:\nتعليمات إضافية:"
        elif note_type == 'general':
            prefill_notes = "مذكرة عامة:\nالموضوع:\nتفاصيل:\nتعليمات للمريض:"
        
        if request.method == 'POST':
            medical_notes = request.form.get('medical_notes')
            if medical_notes:
                # إضافة الملاحظات الطبية
                if not visit.notes:
                    visit.notes = ""
                label = '[ملاحظات طبية]'
                if note_type == 'lab':
                    label = '[مذكرة تحاليل]'
                elif note_type == 'radiology':
                    label = '[مذكرة تصوير]'
                elif note_type == 'general':
                    label = '[مذكرة عامة]'
                from datetime import timezone
                visit.notes += f"\n{label} - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} - الطبيب: {current_user.full_name}\n{medical_notes}"
                db.session.commit()
                try:
                    db.session.add(AuditTrail(
                        entity_type='visit',
                        entity_id=visit_id,
                        action='update',
                        user_id=current_user.id,
                        user_ip=request.remote_addr,
                        user_agent=request.headers.get('User-Agent'),
                        description='إضافة ملاحظات طبية'
                    ))
                    db.session.commit()
                except Exception:

                    logging.warning(f"Error in {__name__}: {e}")
                flash('تم حفظ الملاحظات الطبية بنجاح', 'success')
                return redirect(url_for('doctor.patient_queue'))
        
        return render_template('doctor/notes.html', visit=visit, note_type=note_type, prefill_notes=prefill_notes)
    except Exception as e:
        logging.exception("Error in notes")
        if current_app.config.get('TESTING'):
            raise
        flash('حدث خطأ في حفظ الملاحظات', 'error')
        return redirect(url_for('doctor.patient_queue'))


@doctor_bp.route('/api/note-templates', methods=['GET'])
@login_required
@role_required('doctor', 'admin', 'manager', 'super_admin')
def api_note_templates():
    templates = _get_doctor_note_templates()
    active_only = (request.args.get('active_only') or 'true').strip().lower() in {'1', 'true', 'yes', 'on'}
    out = []
    for t in templates:
        if not isinstance(t, dict):
            continue
        if active_only and not t.get('is_active', True):
            continue
        out.append(t)
    return jsonify({'success': True, 'templates': out}), 200

@doctor_bp.route('/api/dashboard-layout', methods=['GET', 'POST'])
@login_required
@role_required('doctor', 'admin', 'manager', 'super_admin')
def api_dashboard_layout():
    if request.method == 'GET':
        return jsonify({'success': True, 'items': _get_doctor_dashboard_layout()}), 200
    data = request.get_json() or {}
    items = data.get('items') or []
    allowed = {i['id'] for i in _default_doctor_dashboard_layout()}
    normalized = []
    for item in items:
        if not isinstance(item, dict):
            continue
        panel_id = item.get('id')
        if panel_id not in allowed:
            continue
        normalized.append({
            'id': panel_id,
            'title': item.get('title') or '',
            'order': int(item.get('order') or 0),
            'enabled': bool(item.get('enabled', True))
        })
    if not normalized:
        normalized = _default_doctor_dashboard_layout()
    _save_doctor_dashboard_layout(normalized)
    return jsonify({'success': True, 'items': normalized}), 200


@doctor_bp.route('/api/note-templates', methods=['POST'])
@login_required
@role_required('doctor', 'admin', 'manager', 'super_admin')
def upsert_note_template():
    payload = request.get_json(silent=True) if request.is_json else request.form
    template_id = (payload.get('id') or '').strip() or None
    name = (payload.get('name') or '').strip()
    text = payload.get('text') or ''
    is_active = payload.get('is_active')
    if isinstance(is_active, str):
        is_active = is_active.strip().lower() in {'1', 'true', 'yes', 'on'}
    if is_active is None:
        is_active = True
    if not name:
        return jsonify({'success': False, 'message': 'اسم القالب مطلوب'}), 400

    templates = _get_doctor_note_templates()
    if template_id:
        updated = False
        for t in templates:
            if isinstance(t, dict) and t.get('id') == template_id:
                t['name'] = name
                t['text'] = text
                t['is_active'] = bool(is_active)
                updated = True
                break
        if not updated:
            return jsonify({'success': False, 'message': 'القالب غير موجود'}), 404
        _save_doctor_note_templates(templates)
        return jsonify({'success': True, 'id': template_id}), 200

    new_id = secrets.token_hex(8)
    templates.append({'id': new_id, 'name': name, 'text': text, 'is_active': bool(is_active)})
    _save_doctor_note_templates(templates)
    return jsonify({'success': True, 'id': new_id}), 201


@doctor_bp.route('/api/note-templates/<string:template_id>/delete', methods=['POST'])
@login_required
@role_required('doctor', 'admin', 'manager', 'super_admin')
def delete_note_template(template_id: str):
    templates = _get_doctor_note_templates()
    before = len(templates)
    templates = [t for t in templates if not (isinstance(t, dict) and t.get('id') == template_id)]
    if len(templates) == before:
        return jsonify({'success': False, 'message': 'القالب غير موجود'}), 404
    _save_doctor_note_templates(templates)
    return jsonify({'success': True}), 200
