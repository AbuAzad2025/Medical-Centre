"""
مسارات الأشعة - Radiology Routes
Medical System Radiology Routes
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, send_file, current_app
from flask_login import login_required, current_user
from utils.decorators import role_required
from models.patient import Patient
from models.visit import Visit
from models.user import User
from models.radiology_request import RadiologyRequest
from models.radiology_test import RadiologyResult
from models.file_management import FileUpload
from models.system_config import SystemConfig
from app_factory import db
import logging
from datetime import datetime, date, timezone
from datetime import timedelta
import json
import os
from werkzeug.utils import secure_filename
import base64
from io import BytesIO
import qrcode
import secrets

radiology_bp = Blueprint('radiology', __name__)

def _log_radiology_workflow(request_id, status, action, notes=None):
    try:
        from models.request_workflow import RequestWorkflow
        db.session.add(RequestWorkflow(
            request_id=request_id,
            request_type='radiology',
            department='radiology',
            status=status,
            action=action,
            notes=notes,
            timestamp=datetime.now(timezone.utc),
            user_id=getattr(current_user, 'id', None) or 0
        ))
    except Exception:
        pass

@radiology_bp.route('/')
@login_required
def index():
    return redirect(url_for('radiology.dashboard'))

@radiology_bp.route('/quality')
@login_required
@role_required('radiology', 'admin', 'manager')
def quality():
    start_raw = (request.args.get('start_date') or '').strip()
    end_raw = (request.args.get('end_date') or '').strip()
    try:
        start_date = datetime.strptime(start_raw, '%Y-%m-%d').date() if start_raw else (date.today().replace(day=1))
    except Exception:
        start_date = date.today().replace(day=1)
    try:
        end_date = datetime.strptime(end_raw, '%Y-%m-%d').date() if end_raw else date.today()
    except Exception:
        end_date = date.today()

    start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)

    done_q = RadiologyRequest.query.filter(
        RadiologyRequest.status == 'DONE',
        RadiologyRequest.updated_at >= start_dt,
        RadiologyRequest.updated_at <= end_dt
    )
    total_done = done_q.count()

    try:
        avg_tat_seconds = db.session.query(
            db.func.avg(db.func.extract('epoch', RadiologyRequest.updated_at) - db.func.extract('epoch', RadiologyRequest.created_at))
        ).filter(
            RadiologyRequest.status == 'DONE',
            RadiologyRequest.updated_at >= start_dt,
            RadiologyRequest.updated_at <= end_dt
        ).scalar()
    except Exception:
        db.session.rollback()
        avg_tat_seconds = None
    avg_tat_minutes = float(avg_tat_seconds or 0) / 60.0 if avg_tat_seconds is not None else 0.0

    total_validated_results = db.session.query(db.func.count(RadiologyResult.id)).join(
        RadiologyRequest, RadiologyRequest.id == RadiologyResult.request_id
    ).filter(
        RadiologyRequest.status == 'DONE',
        RadiologyRequest.updated_at >= start_dt,
        RadiologyRequest.updated_at <= end_dt,
        RadiologyResult.status == 'VALIDATED'
    ).scalar() or 0

    critical_validated_results = db.session.query(db.func.count(RadiologyResult.id)).join(
        RadiologyRequest, RadiologyRequest.id == RadiologyResult.request_id
    ).filter(
        RadiologyRequest.status == 'DONE',
        RadiologyRequest.updated_at >= start_dt,
        RadiologyRequest.updated_at <= end_dt,
        RadiologyResult.status == 'VALIDATED',
        RadiologyResult.is_critical == True
    ).scalar() or 0

    critical_ratio = (float(critical_validated_results) / float(total_validated_results)) if total_validated_results else 0.0

    modality_rows = []
    try:
        rows = db.session.query(
            db.func.upper(RadiologyRequest.modality).label('modality'),
            db.func.count(RadiologyRequest.id).label('cnt'),
            db.func.avg(db.func.extract('epoch', RadiologyRequest.updated_at) - db.func.extract('epoch', RadiologyRequest.created_at)).label('avg_sec'),
        ).filter(
            RadiologyRequest.status == 'DONE',
            RadiologyRequest.updated_at >= start_dt,
            RadiologyRequest.updated_at <= end_dt
        ).group_by(db.func.upper(RadiologyRequest.modality)).order_by(db.func.count(RadiologyRequest.id).desc()).all()
        for r in rows:
            modality_rows.append({
                'modality': (r.modality or 'N/A'),
                'count': int(r.cnt or 0),
                'avg_minutes': float(r.avg_sec or 0) / 60.0
            })
    except Exception:
        modality_rows = []

    return render_template(
        'radiology/quality.html',
        start_date=start_date,
        end_date=end_date,
        total_done=total_done,
        avg_tat_minutes=avg_tat_minutes,
        total_validated_results=int(total_validated_results),
        critical_validated_results=int(critical_validated_results),
        critical_ratio=critical_ratio,
        modality_rows=modality_rows
    )

def _radiology_templates_cfg():
    return SystemConfig.query.filter_by(config_key='radiology_report_templates').first()

def _radiology_macros_cfg():
    return SystemConfig.query.filter_by(config_key='radiology_report_macros').first()

def _default_radiology_report_templates():
    return [
        {
            'id': secrets.token_hex(8),
            'name': 'X-Ray قالب عام',
            'modality': 'XRAY',
            'findings': "الطريقة (Technique):\nأشعة سينية لـ {{BODY_PART}} (Views: ________)\n\nالموجودات (Findings):\n- العظام/المفاصل: ________________________\n- النسج الرخوة: _________________________\n- ملاحظات إضافية: _______________________\n",
            'impression': "الخلاصة (Impression):\n1) ________________________\n2) ________________________\n",
            'recommendations': "التوصيات:\n- ربط النتائج بالسياق السريري.\n- متابعة/تصوير إضافي عند الحاجة.\n",
            'is_active': True
        },
        {
            'id': secrets.token_hex(8),
            'name': 'CT قالب عام',
            'modality': 'CT',
            'findings': "الطريقة (Technique):\nCT لـ {{BODY_PART}} (مع/بدون مادة ظليلة: ________) (Slice thickness: ________)\n\nالموجودات (Findings):\n- الأعضاء/البنى ذات الصلة: ________________________\n- العقد/السوائل/النزف: ___________________________\n- ملاحظات إضافية: _______________________________\n",
            'impression': "الخلاصة (Impression):\n1) ________________________\n2) ________________________\n",
            'recommendations': "التوصيات:\n- ربط النتائج بالسياق السريري.\n- متابعة/استشارة اختصاصية عند الحاجة.\n",
            'is_active': True
        },
        {
            'id': secrets.token_hex(8),
            'name': 'MRI قالب عام',
            'modality': 'MRI',
            'findings': "الطريقة (Technique):\nMRI لـ {{BODY_PART}} (Sequences: ________) (مع/بدون مادة ظليلة: ________)\n\nالموجودات (Findings):\n- التغيرات البنيوية/الإشارة: ________________________\n- السوائل/الكتل/الآفات: ____________________________\n- ملاحظات إضافية: ________________________________\n",
            'impression': "الخلاصة (Impression):\n1) ________________________\n2) ________________________\n",
            'recommendations': "التوصيات:\n- ربط النتائج بالسياق السريري.\n- متابعة/تصوير إضافي عند الحاجة.\n",
            'is_active': True
        }
    ]

def _default_radiology_report_macros():
    return [
        {'id': secrets.token_hex(8), 'name': 'Normal', 'text': 'لا توجد موجودات حادة. ضمن الحدود الطبيعية.', 'is_active': True},
        {'id': secrets.token_hex(8), 'name': 'Recommend Follow-up', 'text': 'يوصى بالمتابعة وربط النتائج بالسياق السريري.', 'is_active': True},
        {'id': secrets.token_hex(8), 'name': 'Limited Study', 'text': 'الدراسة محدودة بسبب ________. يوصى بإعادة التصوير عند الحاجة.', 'is_active': True},
    ]

def _get_radiology_report_templates():
    cfg = _radiology_templates_cfg()
    if not cfg:
        cfg = SystemConfig(
            config_key='radiology_report_templates',
            config_type='json',
            config_value='[]',
            category='general',
            description='قوالب تقارير الأشعة',
            is_system=False,
            is_encrypted=False,
            created_by=getattr(current_user, 'id', None),
            updated_by=getattr(current_user, 'id', None),
        )
        db.session.add(cfg)
        templates = _default_radiology_report_templates()
        cfg.set_value(templates)
        db.session.commit()
        return templates

    templates = cfg.get_value() if cfg.config_type == 'json' else []
    if not isinstance(templates, list):
        templates = []
    if not templates:
        templates = _default_radiology_report_templates()
        cfg.set_value(templates)
        cfg.updated_by = getattr(current_user, 'id', None)
        db.session.commit()
    return templates

def _save_radiology_report_templates(templates):
    cfg = _radiology_templates_cfg()
    if not cfg:
        cfg = SystemConfig(
            config_key='radiology_report_templates',
            config_type='json',
            config_value='[]',
            category='general',
            description='قوالب تقارير الأشعة',
            is_system=False,
            is_encrypted=False,
            created_by=getattr(current_user, 'id', None),
            updated_by=getattr(current_user, 'id', None),
        )
        db.session.add(cfg)
    if not isinstance(templates, list):
        templates = []
    cfg.config_type = 'json'
    cfg.set_value(templates)
    cfg.updated_by = getattr(current_user, 'id', None)
    db.session.commit()

def _get_radiology_report_macros():
    cfg = _radiology_macros_cfg()
    if not cfg:
        cfg = SystemConfig(
            config_key='radiology_report_macros',
            config_type='json',
            config_value='[]',
            category='general',
            description='ماكروز تقارير الأشعة',
            is_system=False,
            is_encrypted=False,
            created_by=getattr(current_user, 'id', None),
            updated_by=getattr(current_user, 'id', None),
        )
        db.session.add(cfg)
        macros = _default_radiology_report_macros()
        cfg.set_value(macros)
        db.session.commit()
        return macros

    macros = cfg.get_value() if cfg.config_type == 'json' else []
    if not isinstance(macros, list):
        macros = []
    if not macros:
        macros = _default_radiology_report_macros()
        cfg.set_value(macros)
        cfg.updated_by = getattr(current_user, 'id', None)
        db.session.commit()
    return macros

def _save_radiology_report_macros(macros):
    cfg = _radiology_macros_cfg()
    if not cfg:
        cfg = SystemConfig(
            config_key='radiology_report_macros',
            config_type='json',
            config_value='[]',
            category='general',
            description='ماكروز تقارير الأشعة',
            is_system=False,
            is_encrypted=False,
            created_by=getattr(current_user, 'id', None),
            updated_by=getattr(current_user, 'id', None),
        )
        db.session.add(cfg)
    if not isinstance(macros, list):
        macros = []
    cfg.config_type = 'json'
    cfg.set_value(macros)
    cfg.updated_by = getattr(current_user, 'id', None)
    db.session.commit()

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

@radiology_bp.route('/dashboard')
@login_required
@role_required('radiology', 'manager')
def dashboard():
    """لوحة تحكم الأشعة الذكية"""
    
    
    try:
        today_requests = RadiologyRequest.query.filter(
            db.func.date(RadiologyRequest.created_at) == date.today()
        ).count()
        pending_requests = RadiologyRequest.query.filter(
            RadiologyRequest.status.in_(['REQUESTED', 'IN_PROGRESS'])
        ).count()
        completed_today = RadiologyRequest.query.filter(
            RadiologyRequest.status == 'DONE',
            db.func.date(RadiologyRequest.updated_at) == date.today()
        ).count()
        requested_count = RadiologyRequest.query.filter(
            RadiologyRequest.status == 'REQUESTED'
        ).count()
        in_progress_count = RadiologyRequest.query.filter(
            RadiologyRequest.status == 'IN_PROGRESS'
        ).count()
        done_today_count = RadiologyRequest.query.filter(
            RadiologyRequest.status == 'DONE',
            db.func.date(RadiologyRequest.updated_at) == date.today()
        ).count()
        smart_analytics = get_radiology_smart_analytics()
        imaging_optimization = get_radiology_imaging_optimization()
        quality_assurance = get_radiology_quality_assurance()
        equipment_status = get_radiology_equipment_status()
        report_analysis = get_radiology_report_analysis()
        workflow_automation = get_radiology_workflow_automation()
        predictive_insights = get_radiology_predictive_insights()
        recent_requests = RadiologyRequest.query.order_by(RadiologyRequest.created_at.desc()).limit(10).all()
        stats = {
            'today_requests': today_requests,
            'pending_requests': pending_requests,
            'completed_today': completed_today,
            'requested_count': requested_count,
            'in_progress_count': in_progress_count,
            'done_today_count': done_today_count,
            'smart_analytics': smart_analytics,
            'imaging_optimization': imaging_optimization,
            'quality_assurance': quality_assurance,
            'equipment_status': equipment_status,
            'report_analysis': report_analysis,
            'workflow_automation': workflow_automation,
            'predictive_insights': predictive_insights
        }
        return render_template('radiology/dashboard_new.html', stats=stats, recent_requests=recent_requests)
    
    except Exception as e:
        logging.error(f"Error in radiology dashboard: {str(e)}")
        flash('حدث خطأ في تحميل لوحة التحكم', 'error')
        return redirect(url_for('main.dashboard'))

@radiology_bp.route('/requests')
@login_required
@role_required('radiology', 'manager')
def requests():
    """طلبات الأشعة"""
    
    
    return render_template('radiology/radiology_requests.html')

@radiology_bp.route('/reports')
@login_required
@role_required('radiology', 'manager')
def reports():
    """تقارير الأشعة"""
    
    request_id = request.args.get('request_id', type=int)
    radiology_request = None
    if request_id:
        radiology_request = db.session.get(RadiologyRequest, request_id)
    if not radiology_request:
        radiology_request = RadiologyRequest.query.order_by(RadiologyRequest.created_at.desc()).first()
    radiology_result = radiology_request.results[0] if radiology_request and radiology_request.results else None
    recent_requests = RadiologyRequest.query.order_by(RadiologyRequest.created_at.desc()).limit(20).all()
    return render_template(
        'radiology/radiology_report_form.html',
        radiology_request=radiology_request,
        radiology_result=radiology_result,
        recent_requests=recent_requests,
        today=date.today().strftime('%Y-%m-%d')
    )

@radiology_bp.route('/images')
@login_required
@role_required('radiology', 'manager')
def images():
    """صور الأشعة"""
    
    
    return render_template('radiology/view_request.html')

@radiology_bp.route('/tests')
@login_required
@role_required('radiology', 'manager')
def tests():
    """فحوصات الأشعة"""
    
    
    return render_template('radiology/add_scan.html')

@radiology_bp.route('/print_report/<int:radiology_scan_id>', methods=['GET'])
@login_required
@role_required('radiology', 'manager')
def print_report(radiology_scan_id=None):
    """طباعة تقرير الأشعة"""
    
    try:
        if radiology_scan_id is None:
            flash('المعرف غير محدد', 'error')
            return redirect(url_for('radiology.reports'))
        result = db.session.get(RadiologyResult, radiology_scan_id)
        if not result:
            req = db.session.get(RadiologyRequest, radiology_scan_id)
            if not req or not req.results:
                flash('نتيجة الأشعة غير موجودة', 'error')
                return redirect(url_for('radiology.reports'))
            result = req.results[0]
        payload = f"RAD|{result.id}|{result.patient_id}|{result.created_at.isoformat()}"
        img = qrcode.make(payload)
        buf = BytesIO()
        img.save(buf, format='PNG')
        qr_data_uri = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('utf-8')
        return render_template('print/radiology_report.html', radiology_result=result, qr_data_uri=qr_data_uri)
    except Exception as e:
        logging.error(f"Error printing radiology report {radiology_scan_id}: {str(e)}")
        flash('حدث خطأ في طباعة تقرير الأشعة', 'error')
        return redirect(url_for('radiology.reports'))

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

def get_radiology_smart_analytics():
    """التحليلات الذكية للأشعة"""
    try:
        total_requests = RadiologyRequest.query.count()
        completed_requests = RadiologyRequest.query.filter(RadiologyRequest.status == 'DONE').count()
        pending_requests = RadiologyRequest.query.filter(
            RadiologyRequest.status.in_(['REQUESTED', 'IN_PROGRESS'])
        ).count()
        completion_rate = (completed_requests / total_requests * 100) if total_requests > 0 else 0
        try:
            avg_processing_seconds = db.session.query(
                db.func.avg(db.func.extract('epoch', RadiologyRequest.updated_at) - db.func.extract('epoch', RadiologyRequest.created_at))
            ).filter(RadiologyRequest.status == 'DONE').scalar()
        except Exception:
            db.session.rollback()
            avg_processing_seconds = None
        avg_processing_time = round((float(avg_processing_seconds or 0) / 3600.0), 2)
        return {
            'total_requests': total_requests,
            'completion_rate': round(completion_rate, 2),
            'pending_requests': pending_requests,
            'avg_processing_time': avg_processing_time,
            'efficiency_score': calculate_radiology_efficiency(completion_rate, pending_requests),
            'status': 'excellent' if completion_rate > 90 else 'good' if completion_rate > 70 else 'needs_improvement'
        }
    except Exception as e:
        logging.error(f"Error getting radiology smart analytics: {str(e)}")
        return {}

def get_radiology_imaging_optimization():
    """تحسين التصوير"""
    try:
        total_requests = RadiologyRequest.query.count()
        try:
            avg_processing_seconds = db.session.query(
                db.func.avg(db.func.extract('epoch', RadiologyRequest.updated_at) - db.func.extract('epoch', RadiologyRequest.created_at))
            ).filter(RadiologyRequest.status == 'DONE').scalar()
        except Exception:
            db.session.rollback()
            avg_processing_seconds = None
        avg_imaging_time = round((float(avg_processing_seconds or 0) / 3600.0), 2)
        total_processed = RadiologyRequest.query.filter(RadiologyRequest.status == 'DONE').count()
        suggestions = generate_imaging_optimization_suggestions(avg_imaging_time)
        return {
            'avg_imaging_time': avg_imaging_time,
            'total_processed': total_processed,
            'optimization_suggestions': suggestions,
            'efficiency_score': calculate_imaging_efficiency(avg_imaging_time, total_requests)
        }
    except Exception as e:
        logging.error(f"Error getting radiology imaging optimization: {str(e)}")
        return {}

def get_radiology_quality_assurance():
    """ضمان الجودة"""
    try:
        total_done = RadiologyRequest.query.filter(RadiologyRequest.status == 'DONE').count()
        reviewed = RadiologyResult.query.filter(RadiologyResult.reviewed_at.isnot(None)).count()
        critical = RadiologyResult.query.filter(RadiologyResult.is_critical == True).count()
        quality_score = (reviewed / total_done * 100) if total_done else 100
        return {
            'total_completed': total_done,
            'quality_score': round(quality_score, 2),
            'standard_deviations': round((critical / total_done) * 3, 2) if total_done else 0,
            'recheck_requests': RadiologyResult.query.filter(RadiologyResult.revised_after_review == True).count()
        }
    except Exception as e:
        logging.error(f"Error getting radiology quality assurance: {str(e)}")
        return {}

def get_radiology_equipment_status():
    """حالة المعدات"""
    try:
        equipment_status = {
            'xray_machines': 'operational',
            'ct_scanner': 'operational',
            'mri_machine': 'operational',
            'ultrasound': 'maintenance'
        }
        total_equipment = len(equipment_status)
        operational = len([v for v in equipment_status.values() if v == 'operational'])
        maintenance = len([v for v in equipment_status.values() if v == 'maintenance'])
        efficiency = round((operational / total_equipment) * 100, 2) if total_equipment else 0
        return {
            'total_equipment': total_equipment,
            'operational': operational,
            'maintenance': maintenance,
            'efficiency': efficiency
        }
    except Exception as e:
        logging.error(f"Error getting radiology equipment status: {str(e)}")
        return {}

def get_radiology_report_analysis():
    """تحليل التقارير"""
    try:
        total_reports = RadiologyResult.query.count()
        abnormal_findings = RadiologyResult.query.filter(
            RadiologyResult.status.in_(['READY', 'VALIDATED'])
        ).count()
        critical_reports = RadiologyResult.query.filter(RadiologyResult.is_critical == True).count()
        abnormal_rate = (abnormal_findings / total_reports * 100) if total_reports else 0
        last_7 = RadiologyResult.query.filter(RadiologyResult.created_at >= (date.today() - timedelta(days=7))).count()
        prev_7 = RadiologyResult.query.filter(
            RadiologyResult.created_at >= (date.today() - timedelta(days=14)),
            RadiologyResult.created_at < (date.today() - timedelta(days=7))
        ).count()
        trend_analysis = 'تصاعدي' if last_7 > prev_7 else 'تنازلي' if last_7 < prev_7 else 'مستقر'
        return {
            'total_reports': total_reports,
            'abnormal_findings': abnormal_findings,
            'abnormal_rate': round(abnormal_rate, 2),
            'critical_reports': critical_reports,
            'trend_analysis': trend_analysis
        }
    except Exception as e:
        logging.error(f"Error getting radiology report analysis: {str(e)}")
        return {}

def get_radiology_workflow_automation():
    """أتمتة سير العمل"""
    try:
        total_requests = RadiologyRequest.query.count()
        done_requests = RadiologyRequest.query.filter(RadiologyRequest.status == 'DONE').count()
        automation_rate = round((done_requests / total_requests) * 100, 2) if total_requests else 0
        automated_tasks = done_requests
        time_saved = round(automation_rate * 1.1, 2)
        efficiency_gain = round(automation_rate * 0.7, 2)
        return {
            'automated_tasks': automated_tasks,
            'automation_rate': automation_rate,
            'time_saved': time_saved,
            'efficiency_gain': efficiency_gain
        }
    except Exception as e:
        logging.error(f"Error getting radiology workflow automation: {str(e)}")
        return {}

def get_radiology_predictive_insights():
    try:
        today = date.today()
        week_start = today - timedelta(days=7)
        month_start = today - timedelta(days=30)
        weekly_requests = RadiologyRequest.query.filter(RadiologyRequest.created_at >= week_start).count()
        monthly_requests = RadiologyRequest.query.filter(RadiologyRequest.created_at >= month_start).count()
        prev_week = RadiologyRequest.query.filter(
            RadiologyRequest.created_at >= today - timedelta(days=14),
            RadiologyRequest.created_at < week_start
        ).count()
        growth_rate = ((weekly_requests - prev_week) / prev_week * 100) if prev_week else 0
        predicted_demand = int(round((weekly_requests / 7) * 7))
        return {
            'weekly_requests': weekly_requests,
            'monthly_requests': monthly_requests,
            'predicted_demand': predicted_demand,
            'growth_rate': round(growth_rate, 2)
        }
    except Exception:
        return {}

def calculate_radiology_efficiency(completion_rate, pending_requests):
    """حساب كفاءة الأشعة"""
    try:
        base_score = completion_rate
        penalty = min(pending_requests * 2.5, 25)  # خصم لكل طلب معلق
        return max(base_score - penalty, 0)
    except:
        return 0

def calculate_imaging_efficiency(avg_time, total_requests):
    """حساب كفاءة التصوير"""
    try:
        if avg_time <= 1.5:  # ساعة ونصف أو أقل
            return 95
        elif avg_time <= 3:  # 3 ساعات أو أقل
            return 85
        elif avg_time <= 4.5:  # 4.5 ساعات أو أقل
            return 75
        else:
            return 60
    except:
        return 0

def generate_imaging_optimization_suggestions(avg_time):
    """توليد اقتراحات تحسين التصوير"""
    suggestions = []
    
    if avg_time > 3:
        suggestions.append("تحسين تدفق المرضى")
    if avg_time > 4:
        suggestions.append("إضافة معدات تصوير جديدة")
    if avg_time > 5:
        suggestions.append("زيادة عدد الفنيين")
    
    return suggestions
@radiology_bp.route('/worklist')
@login_required
@role_required('radiology', 'technician', 'admin', 'manager')
def worklist():
    try:
        today = date.today()
        counts = {
            'requested': RadiologyRequest.query.filter(RadiologyRequest.status == 'REQUESTED').count(),
            'in_progress': RadiologyRequest.query.filter(RadiologyRequest.status == 'IN_PROGRESS').count(),
            'done_today': RadiologyRequest.query.filter(
                RadiologyRequest.status == 'DONE',
                db.func.date(RadiologyRequest.updated_at) == today
            ).count()
        }

        status = request.args.get('status') or 'REQUESTED'
        q = RadiologyRequest.query
        if status == 'DONE_TODAY':
            q = q.filter(RadiologyRequest.status == 'DONE', db.func.date(RadiologyRequest.updated_at) == today)
        elif status:
            q = q.filter(RadiologyRequest.status == status)

        requests_list = q.order_by(RadiologyRequest.created_at.desc()).all()
        visits_by_id = {}
        try:
            visit_ids = [r.visit_id for r in requests_list if getattr(r, 'visit_id', None)]
            if visit_ids:
                visits = Visit.query.filter(Visit.id.in_(visit_ids)).all()
                visits_by_id = {v.id: v for v in visits}
        except Exception:
            visits_by_id = {}
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
        rad_request = db.session.get(RadiologyRequest, request_id)
        if not rad_request:
            flash('الطلب غير موجود', 'error')
            return redirect(url_for('radiology.worklist'))

        existing_result = rad_request.results[0] if rad_request.results else None
        uploads = []
        if existing_result:
            uploads = FileUpload.query.filter_by(
                related_entity_type='radiology_result',
                related_entity_id=existing_result.id
            ).order_by(FileUpload.uploaded_at.desc()).all()

        visit_summary = db.session.get(Visit, rad_request.visit_id) if getattr(rad_request, 'visit_id', None) else None
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
        req = db.session.get(RadiologyRequest, request_id)
        if not req or req.status not in ('REQUESTED',):
            if request.accept_mimetypes.best == 'application/json':
                return jsonify({'success': False, 'message': 'الطلب غير صالح'}), 400
            flash('الطلب غير صالح', 'error')
            return redirect(url_for('radiology.worklist'))
        req.status = 'IN_PROGRESS'
        req.updated_at = datetime.now(timezone.utc)
        _log_radiology_workflow(req.id, 'IN_PROGRESS', 'claim')
        db.session.commit()
        if request.accept_mimetypes.best == 'application/json':
            return jsonify({'success': True, 'message': 'تم استلام الطلب'}), 200
        flash('تم استلام الطلب', 'success')
        return redirect(url_for('radiology.worklist', status='IN_PROGRESS'))
    except Exception as e:
        db.session.rollback()
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
        if request.is_json:
            payload = request.get_json() or {}
        else:
            payload = dict(request.form) if request.form else {}

        existing_result = req.results[0] if req.results else None
        is_critical_raw = (payload.get('is_critical') if payload else None)
        if isinstance(is_critical_raw, list):
            is_critical_raw = is_critical_raw[0] if is_critical_raw else None
        is_critical = False
        if isinstance(is_critical_raw, str):
            is_critical = is_critical_raw.strip().lower() in {'1', 'true', 'yes', 'on'}
        elif isinstance(is_critical_raw, (bool, int)):
            is_critical = bool(is_critical_raw)
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

        files = request.files.getlist('image_upload') if request.files else []
        if files:
            upload_root = current_app.config.get('UPLOAD_FOLDER') or os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'static', 'uploads')
            target_dir = os.path.join(upload_root, 'radiology', str(res.id))
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
                    filename=stored_name,
                    original_filename=original_name,
                    file_path=file_path,
                    file_size=(size or 1),
                    file_type=(getattr(f, 'mimetype', None) or 'application/octet-stream'),
                    file_extension=(ext.lower().lstrip('.') or 'bin'),
                    description=(payload.get('file_description') if payload else None),
                    related_entity_type='radiology_result',
                    related_entity_id=res.id,
                    uploaded_by=current_user.id
                )
                db.session.add(fu)

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

        try:
            from services.notification_service import NotificationService
            doctor_id = req.requester.id if req.requester else None
            if doctor_id:
                urgent = bool(is_critical)
                NotificationService.send_notification(
                    recipient_id=doctor_id,
                    title='نتيجة الأشعة جاهزة',
                    message=f'تم اعتماد تقرير الأشعة لطلب #{req.id}' + (' (حرج)' if urgent else ''),
                    notification_type=('warning' if urgent else 'info'),
                    is_urgent=urgent,
                    
                )
                if urgent:
                    NotificationService.send_notification(
                        recipient_role='reception',
                        title='نتيجة أشعة حرجة',
                        message=f'يوجد تقرير أشعة حرج لطلب #{req.id} للمريض #{req.patient_id}',
                        notification_type='warning',
                        is_urgent=True
                    )
        except Exception:
            pass

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

@radiology_bp.route('/api/ai-assist', methods=['POST'])
@login_required
@role_required('radiology', 'doctor', 'admin', 'manager')
def api_ai_assist():
    try:
        data = request.get_json() or {}
        modality = (data.get('modality') or '').strip().upper()
        body_part = (data.get('body_part') or '').strip().lower()
        impression = (data.get('impression') or '').strip().lower()
        study_uid = (data.get('study_uid') or '').strip()
        pacs_url = (data.get('pacs_url') or '').strip()

        suggestions = []
        if modality == 'CT' and ('brain' in body_part or 'دماغ' in body_part):
            suggestions.append('تقييم نزف حاد أو كتلة داخل القحف إذا كانت الأعراض مناسبة.')
        if modality in {'XRAY', 'X-RAY', 'XR'} and ('chest' in body_part or 'صدر' in body_part):
            suggestions.append('تأكد من مراجعة علامات الارتشاح الرئوي والانصباب الجنبي.')
        if modality == 'US' and ('abdomen' in body_part or 'بطن' in body_part):
            suggestions.append('راجع المرارة والكبد والكلى بحثاً عن مؤشرات انسداد.')
        if 'نزف' in impression or 'bleed' in impression:
            suggestions.append('النتيجة توحي بخطورة محتملة، يوصى بإبلاغ الطبيب فوراً.')
        if not suggestions:
            suggestions.append('لا توجد توصيات آلية واضحة، يرجى ربط النتائج بالسياق السريري.')

        payload = {
            'suggestions': suggestions,
            'disclaimer': 'مخرجات مساعدة وليست تشخيصاً نهائياً.',
            'external_ref': pacs_url or (f"study:{study_uid}" if study_uid else None)
        }
        return jsonify({'success': True, 'data': payload}), 200
    except Exception as e:
        logging.error(f"Error generating radiology AI assist: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر توليد توصيات AI'}), 500


@radiology_bp.route('/results/<int:result_id>/second-review', methods=['POST'])
@login_required
@role_required('radiology', 'admin', 'manager', 'super_admin')
def second_review_result(result_id):
    try:
        from models.radiology_test import RadiologyResult
        res = db.session.get(RadiologyResult, result_id)
        if not res:
            return jsonify({'success': False, 'message': 'النتيجة غير موجودة'}), 404
        res.reviewed_by = current_user.id
        res.reviewed_at = datetime.now(timezone.utc)
        db.session.commit()
        return jsonify({'success': True}), 200
    except Exception as e:
        db.session.rollback()
        logging.error(f"Second review radiology result error: {str(e)}")
        return jsonify({'success': False, 'message': 'تعذر حفظ المراجعة حالياً'}), 500

@radiology_bp.route('/files/<int:file_id>')
@login_required
@role_required('radiology', 'doctor', 'admin', 'manager', 'super_admin')
def download_file(file_id):
    try:
        f = db.session.get(FileUpload, file_id)
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
            db.session.commit()
        except Exception:
            db.session.rollback()
        return send_file(f.file_path, as_attachment=True, download_name=f.original_filename)
    except Exception as e:
        logging.error(f"Error downloading radiology file {file_id}: {str(e)}")
        flash('حدث خطأ في تحميل الملف', 'error')
        return redirect(url_for('radiology.worklist'))

@radiology_bp.route('/api/worklist')
@login_required
@role_required('radiology', 'technician', 'admin', 'manager', 'doctor', 'super_admin')
def api_worklist():
    try:
        visit_id = request.args.get('visit_id', type=int)
        status = request.args.get('status', type=str)
        q = RadiologyRequest.query
        if visit_id:
            q = q.filter(RadiologyRequest.visit_id == visit_id)
        if status:
            q = q.filter(RadiologyRequest.status == status)
        reqs = q.order_by(RadiologyRequest.created_at.desc()).limit(50).all()
        data = []
        for r in reqs:
            data.append({
                'id': r.id,
                'visit_id': r.visit_id,
                'patient_id': r.patient_id,
                'status': r.status,
                'request_number': getattr(r, 'request_number', None)
            })
        return jsonify({'success': True, 'requests': data})
    except Exception as e:
        logging.error(f"Error loading radiology api worklist: {str(e)}")
        return jsonify({'success': False, 'message': 'حدث خطأ'}), 500

@radiology_bp.route('/api/fhir/observation/radiology/<int:result_id>')
@login_required
@role_required('radiology', 'lab', 'doctor', 'admin', 'manager')
def api_fhir_radiology_observation(result_id):
    try:
        res = db.session.get(RadiologyResult, result_id)
        if not res:
            return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'RadiologyResult not found'}]}), 404
        req = db.session.get(RadiologyRequest, res.request_id)
        visit_id = req.visit_id if req else None

        status_map = {
            'PENDING': 'preliminary',
            'READY': 'final',
            'VALIDATED': 'final'
        }
        status = status_map.get((res.status or '').upper(), 'unknown')

        code_text = 'Radiology Observation'
        if req and (req.modality or req.body_part):
            mp = []
            if req.modality:
                mp.append(req.modality)
            if req.body_part:
                mp.append(req.body_part)
            code_text = ' / '.join(mp)

        resource = {
            'resourceType': 'Observation',
            'id': str(res.id),
            'status': status,
            'category': [{'coding': [{'system': 'http://terminology.hl7.org/CodeSystem/observation-category', 'code': 'imaging'}]}],
            'code': {
                'coding': [{'system': 'urn:medical-system:modality', 'code': (req.modality if req and req.modality else 'RAD')}],
                'text': code_text
            },
            'subject': {'reference': f'Patient/{res.patient_id}'},
            **({'encounter': {'reference': f'Encounter/{visit_id}'}} if visit_id else {}),
            'effectiveDateTime': (res.created_at.isoformat() if res.created_at else None),
            'valueString': (res.impression or res.findings or ''),
            **({'performer': [{'reference': f'Practitioner/{res.performed_by}'}]} if res.performed_by else {}),
            'note': ([{'text': res.notes}] if res.notes else []) + ([{'text': f'StudyUID: {res.study_uid}'}] if res.study_uid else [])
        }

        return jsonify(resource)
    except Exception as e:
        logging.error(f"Error exporting FHIR Radiology Observation: {str(e)}")
        return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'تعذر تصدير بيانات الأشعة حالياً'}]}), 500

@radiology_bp.route('/api/fhir/diagnosticreport/radiology/<int:result_id>')
@login_required
@role_required('radiology', 'lab', 'doctor', 'admin', 'manager')
def api_fhir_radiology_diagnostic_report(result_id):
    """تصدير تقرير أشعة بصيغة FHIR DiagnosticReport وربطه بـ Encounter"""
    try:
        res = db.session.get(RadiologyResult, result_id)
        if not res:
            return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'RadiologyResult not found'}]}), 404
        req = db.session.get(RadiologyRequest, res.request_id)
        visit_id = req.visit_id if req else None

        status_map = {
            'PENDING': 'preliminary',
            'READY': 'final',
            'VALIDATED': 'final'
        }
        status = status_map.get((res.status or '').upper(), 'unknown')

        code_text = 'Radiology Report'
        if req and (req.modality or req.body_part):
            mp = []
            if req.modality:
                mp.append(req.modality)
            if req.body_part:
                mp.append(req.body_part)
            code_text = ' / '.join(mp)

        resource = {
            'resourceType': 'DiagnosticReport',
            'id': str(res.id),
            'status': status,
            'category': [{'coding': [{'system': 'http://terminology.hl7.org/CodeSystem/v2-0074', 'code': 'RAD'}]}],
            'code': {
                'coding': [{'system': 'urn:medical-system:modality', 'code': (req.modality if req and req.modality else 'RAD')}],
                'text': code_text
            },
            'subject': {'reference': f'Patient/{res.patient_id}'},
            **({'encounter': {'reference': f'Encounter/{visit_id}'}} if visit_id else {}),
            'effectiveDateTime': (res.created_at.isoformat() if res.created_at else None),
            'issued': (res.updated_at.isoformat() if hasattr(res, 'updated_at') and res.updated_at else None),
            'result': [{'reference': f'Observation/{res.id}'}],
            'conclusion': (res.impression or ''),
            'presentedForm': ([{'contentType': 'text/plain', 'data': base64.b64encode((res.findings or '').encode()).decode()}] if res.findings else []),
            **({'performer': [{'reference': f'Practitioner/{res.performed_by}'}]} if res.performed_by else {})
        }

        return jsonify(resource)
    except Exception as e:
        logging.error(f"Error exporting FHIR Radiology DiagnosticReport: {str(e)}")
        return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'تعذر تصدير تقرير الأشعة حالياً'}]}), 500

@radiology_bp.route('/api/fhir/imagingstudy/<int:result_id>')
@login_required
@role_required('radiology', 'lab', 'doctor', 'admin', 'manager')
def api_fhir_imaging_study(result_id):
    """تصدير دراسة تصويرية بصيغة FHIR ImagingStudy وربطها بـ Encounter"""
    try:
        res = db.session.get(RadiologyResult, result_id)
        if not res:
            return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'تعذر العثور على نتيجة الأشعة المطلوبة'}]}), 404
        req = db.session.get(RadiologyRequest, res.request_id)
        visit_id = req.visit_id if req else None

        resource = {
            'resourceType': 'ImagingStudy',
            'id': str(res.id),
            **({'identifier': [{'system': 'urn:medical-system:study-uid', 'value': res.study_uid}]} if res.study_uid else {}),
            'status': 'available',
            'subject': {'reference': f'Patient/{res.patient_id}'},
            **({'encounter': {'reference': f'Encounter/{visit_id}'}} if visit_id else {}),
            'started': (res.created_at.isoformat() if res.created_at else None),
            **({'modality': [{'system': 'http://dicom.nema.org/resources/ontology/DCM', 'code': req.modality}]} if req and req.modality else {}),
            'numberOfSeries': 1,
            'numberOfInstances': 1,
            'series': [{
                'uid': res.study_uid or f'{res.id}.1',
                'number': 1,
                'modality': {'system': 'http://dicom.nema.org/resources/ontology/DCM', 'code': (req.modality or 'RAD') if req else 'RAD'},
                'bodySite': ({'text': req.body_part} if req and req.body_part else None),
                'instance': [{
                    'uid': f'{res.id}.1.1',
                    'sopClass': {'system': 'urn:ietf:rfc:3986', 'code': 'image/jpeg'},
                    'number': 1
                }]
            }]
        }

        return jsonify(resource)
    except Exception as e:
        logging.error(f"Error exporting FHIR ImagingStudy: {str(e)}")
        return jsonify({'resourceType': 'OperationOutcome', 'issue': [{'severity': 'error', 'diagnostics': 'تعذر تصدير الدراسة التصويرية حالياً'}]}), 500
