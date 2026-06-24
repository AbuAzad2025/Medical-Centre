"""templates routes - extracted from monolithic radiology.py"""

from routes.radiology import (
    radiology_bp,
    _get_radiology_report_templates,
    _save_radiology_report_templates,
    _get_radiology_report_macros,
    _save_radiology_report_macros,
)

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
from app_factory import db
import logging, json, os, base64, secrets
from datetime import datetime, date, timezone, timedelta
from io import BytesIO


# =============================================
# TEMPLATES ROUTES
# =============================================

@radiology_bp.route('/api/report-templates', methods=['GET'])
@login_required
@role_required('radiology', 'manager', 'super_admin')
def api_report_templates():
    templates = _get_radiology_report_templates()
    modality = (request.args.get('modality') or '').strip().upper() or None
    active_only = (request.args.get('active_only') or 'true').strip().lower() in {'1', 'true', 'yes', 'on'}
    out = []
    for t in templates:
        if not isinstance(t, dict):
            continue
        if active_only and not t.get('is_active', True):
            continue
        if modality and (t.get('modality') or '').strip().upper() != modality:
            continue
        out.append(t)
    return jsonify({'success': True, 'templates': out}), 200

@radiology_bp.route('/api/report-templates', methods=['POST'])
@login_required
@role_required('radiology', 'manager', 'super_admin')
def upsert_report_template():
    payload = request.get_json(silent=True) if request.is_json else request.form
    template_id = (payload.get('id') or '').strip() or None
    name = (payload.get('name') or '').strip()
    modality = (payload.get('modality') or '').strip().upper()
    findings = payload.get('findings') or ''
    impression = payload.get('impression') or ''
    recommendations = payload.get('recommendations') or ''
    is_active = payload.get('is_active')
    if isinstance(is_active, str):
        is_active = is_active.strip().lower() in {'1', 'true', 'yes', 'on'}
    if is_active is None:
        is_active = True

    if not name:
        return jsonify({'success': False, 'message': 'اسم القالب مطلوب'}), 400
    if modality not in {'XRAY', 'CT', 'MRI', 'US'}:
        return jsonify({'success': False, 'message': 'نوع الفحص غير صالح'}), 400

    templates = _get_radiology_report_templates()
    if template_id:
        updated = False
        for t in templates:
            if isinstance(t, dict) and t.get('id') == template_id:
                t['name'] = name
                t['modality'] = modality
                t['findings'] = findings
                t['impression'] = impression
                t['recommendations'] = recommendations
                t['is_active'] = bool(is_active)
                updated = True
                break
        if not updated:
            return jsonify({'success': False, 'message': 'القالب غير موجود'}), 404
        _save_radiology_report_templates(templates)
        return jsonify({'success': True, 'id': template_id}), 200

    new_id = secrets.token_hex(8)
    templates.append({
        'id': new_id,
        'name': name,
        'modality': modality,
        'findings': findings,
        'impression': impression,
        'recommendations': recommendations,
        'is_active': bool(is_active)
    })
    _save_radiology_report_templates(templates)
    return jsonify({'success': True, 'id': new_id}), 201

@radiology_bp.route('/api/report-templates/<string:template_id>/delete', methods=['POST'])
@login_required
@role_required('radiology', 'manager', 'super_admin')
def delete_report_template(template_id: str):
    templates = _get_radiology_report_templates()
    before = len(templates)
    templates = [t for t in templates if not (isinstance(t, dict) and t.get('id') == template_id)]
    if len(templates) == before:
        return jsonify({'success': False, 'message': 'القالب غير موجود'}), 404
    _save_radiology_report_templates(templates)
    return jsonify({'success': True}), 200

@radiology_bp.route('/api/report-macros', methods=['GET'])
@login_required
@role_required('radiology', 'manager', 'super_admin')
def api_report_macros():
    macros = _get_radiology_report_macros()
    active_only = (request.args.get('active_only') or 'true').strip().lower() in {'1', 'true', 'yes', 'on'}
    out = []
    for m in macros:
        if not isinstance(m, dict):
            continue
        if active_only and not m.get('is_active', True):
            continue
        out.append(m)
    return jsonify({'success': True, 'macros': out}), 200

@radiology_bp.route('/api/report-macros', methods=['POST'])
@login_required
@role_required('radiology', 'manager', 'super_admin')
def upsert_report_macro():
    payload = request.get_json(silent=True) if request.is_json else request.form
    macro_id = (payload.get('id') or '').strip() or None
    name = (payload.get('name') or '').strip()
    text = payload.get('text') or ''
    is_active = payload.get('is_active')
    if isinstance(is_active, str):
        is_active = is_active.strip().lower() in {'1', 'true', 'yes', 'on'}
    if is_active is None:
        is_active = True
    if not name:
        return jsonify({'success': False, 'message': 'اسم الماكرو مطلوب'}), 400
    macros = _get_radiology_report_macros()
    if macro_id:
        updated = False
        for m in macros:
            if isinstance(m, dict) and m.get('id') == macro_id:
                m['name'] = name
                m['text'] = text
                m['is_active'] = bool(is_active)
                updated = True
                break
        if not updated:
            return jsonify({'success': False, 'message': 'الماكرو غير موجود'}), 404
        _save_radiology_report_macros(macros)
        return jsonify({'success': True, 'id': macro_id}), 200

    new_id = secrets.token_hex(8)
    macros.append({'id': new_id, 'name': name, 'text': text, 'is_active': bool(is_active)})
    _save_radiology_report_macros(macros)
    return jsonify({'success': True, 'id': new_id}), 201

@radiology_bp.route('/api/report-macros/<string:macro_id>/delete', methods=['POST'])
@login_required
@role_required('radiology', 'manager', 'super_admin')
def delete_report_macro(macro_id: str):
    macros = _get_radiology_report_macros()
    before = len(macros)
    macros = [m for m in macros if not (isinstance(m, dict) and m.get('id') == macro_id)]
    if len(macros) == before:
        return jsonify({'success': False, 'message': 'الماكرو غير موجود'}), 404
    _save_radiology_report_macros(macros)
    return jsonify({'success': True}), 200
