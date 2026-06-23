"""
Custom Report Builder
Drag-drop field selection for ad-hoc reports
"""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from utils.decorators import role_required
from app.shared.report_template_service import (
    REPORT_ENTITIES,
    list_templates,
    save_builder_template,
    template_config,
    run_entity_preview,
    render_template_preview,
)
from models.reporting import ReportTemplate

report_builder_bp = Blueprint('report_builder', __name__)

from services.feature_gate_service import guard_module

@report_builder_bp.before_request
def _guard_reporting_module():
    guard_module('reporting')


@report_builder_bp.route('/')
@login_required
@role_required('admin', 'manager', 'accountant', 'doctor')
def builder():
    template_id = request.args.get('template', type=int)
    active_tpl = None
    if template_id:
        active_tpl = ReportTemplate.query.get(template_id)
    return render_template(
        'report_builder/builder.html',
        entities=REPORT_ENTITIES,
        saved_templates=list_templates(),
        active_template=active_tpl,
        active_config=template_config(active_tpl) if active_tpl else None,
    )


@report_builder_bp.route('/preview', methods=['POST'])
@login_required
@role_required('admin', 'manager', 'accountant', 'doctor')
def preview():
    data = request.get_json(silent=True) or {}
    entity = data.get('entity') or request.form.get('entity')
    fields = data.get('fields') or request.form.getlist('fields')
    limit = int(data.get('limit', 100) if data else request.form.get('limit', 100))
    return jsonify(run_entity_preview(entity, fields, limit))


@report_builder_bp.route('/templates', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'accountant', 'doctor')
def templates_list():
    items = [
        {
            'id': t.id,
            'name': t.name,
            'description': t.description,
            'config': template_config(t),
            'updated_at': t.updated_at.isoformat() if t.updated_at else None,
        }
        for t in list_templates()
    ]
    return jsonify({'success': True, 'templates': items})


@report_builder_bp.route('/templates', methods=['POST'])
@login_required
@role_required('admin', 'manager', 'accountant', 'doctor')
def templates_save():
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    entity = data.get('entity')
    fields = data.get('fields') or []
    if not name:
        return jsonify({'success': False, 'message': 'اسم القالب مطلوب'})
    if not entity or entity not in REPORT_ENTITIES:
        return jsonify({'success': False, 'message': 'الكيان غير صالح'})
    if not fields:
        return jsonify({'success': False, 'message': 'اختر حقلاً واحداً على الأقل'})
    try:
        tpl = save_builder_template(
            name=name,
            entity=entity,
            fields=fields,
            user_id=current_user.id,
            description=(data.get('description') or '').strip(),
            template_id=data.get('template_id'),
            limit=int(data.get('limit') or 100),
        )
        return jsonify({'success': True, 'template': tpl.to_dict()})
    except ValueError as exc:
        return jsonify({'success': False, 'message': str(exc)})


@report_builder_bp.route('/templates/<int:template_id>', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'accountant', 'doctor')
def templates_get(template_id: int):
    tpl = ReportTemplate.query.get_or_404(template_id)
    return jsonify({'success': True, 'template': tpl.to_dict(), 'config': template_config(tpl)})


@report_builder_bp.route('/templates/<int:template_id>/run', methods=['POST'])
@login_required
@role_required('admin', 'manager', 'accountant', 'doctor')
def templates_run(template_id: int):
    tpl = ReportTemplate.query.get_or_404(template_id)
    return jsonify(render_template_preview(tpl))
