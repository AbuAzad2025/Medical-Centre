"""ReportTemplate persistence for report_builder — §21.3."""
from __future__ import annotations

import json
from typing import Any

from app_factory import db
from models.reporting import ReportTemplate

REPORT_ENTITIES = {
    'patients': {
        'label': 'المرضى',
        'fields': ['id', 'full_name', 'national_id', 'phone', 'gender', 'birth_date', 'created_at'],
    },
    'visits': {
        'label': 'الزيارات',
        'fields': ['id', 'patient_id', 'visit_type', 'status', 'visit_date', 'total_amount', 'created_at'],
    },
    'appointments': {
        'label': 'المواعيد',
        'fields': ['id', 'patient_id', 'doctor_id', 'starts_at', 'status', 'notes'],
    },
    'invoices': {
        'label': 'الفواتير',
        'fields': ['id', 'patient_id', 'total_amount', 'paid_amount', 'status', 'created_at'],
    },
    'lab_requests': {
        'label': 'طلبات المختبر',
        'fields': ['id', 'patient_id', 'test_name', 'status', 'is_urgent', 'created_at'],
    },
    'prescriptions': {
        'label': 'الوصفات',
        'fields': ['id', 'patient_id', 'doctor_id', 'status', 'created_at'],
    },
}

_MODEL_MAP = {
    'patients': 'Patient',
    'visits': 'Visit',
    'appointments': 'Appointment',
    'invoices': 'Invoice',
    'lab_requests': 'LabRequest',
    'prescriptions': 'Prescription',
}


def run_entity_preview(entity: str, fields: list[str], limit: int = 100) -> dict[str, Any]:
    if not entity or entity not in REPORT_ENTITIES:
        return {'success': False, 'message': 'الكيان غير صالح'}
    model_name = _MODEL_MAP.get(entity)
    if not model_name:
        return {'success': False, 'message': 'الكيان غير مدعوم'}
    try:
        model = getattr(__import__('models', fromlist=[model_name]), model_name)
        query = model.query
        if hasattr(model, 'created_at'):
            query = query.order_by(model.created_at.desc())
        results = query.limit(limit).all()
        output = []
        for row in results:
            item = {}
            for field in fields:
                val = getattr(row, field, None)
                item[field] = str(val) if val is not None else ''
            output.append(item)
        return {'success': True, 'headers': fields, 'rows': output}
    except Exception as exc:
        return {'success': False, 'message': str(exc)}


def list_templates(active_only: bool = True) -> list[ReportTemplate]:
    q = ReportTemplate.query
    if active_only:
        q = q.filter_by(is_active=True)
    return q.order_by(ReportTemplate.updated_at.desc()).all()


def template_config(tpl: ReportTemplate) -> dict[str, Any]:
    try:
        if tpl.template_content and tpl.template_content.strip().startswith('{'):
            return json.loads(tpl.template_content)
    except Exception:
        pass
    return tpl.get_template_variables_dict() or {}


def save_builder_template(
    *,
    name: str,
    entity: str,
    fields: list[str],
    user_id: int | None,
    description: str = '',
    template_id: int | None = None,
    limit: int = 100,
) -> ReportTemplate:
    payload = {
        'entity': entity,
        'fields': fields,
        'limit': limit,
        'builder': 'report_builder_v1',
    }
    if template_id:
        tpl = db.session.get(ReportTemplate, template_id)
        if not tpl:
            raise ValueError('القالب غير موجود')
        tpl.name = name.strip() or tpl.name
        tpl.description = description or tpl.description
        tpl.template_content = json.dumps(payload, ensure_ascii=False)
        tpl.set_template_variables_dict(payload)
    else:
        tpl = ReportTemplate(
            name=name.strip() or 'تقرير مخصص',
            description=description or None,
            template_type='operational',
            template_content=json.dumps(payload, ensure_ascii=False),
            is_active=True,
            created_by=user_id,
        )
        tpl.set_template_variables_dict(payload)
        db.session.add(tpl)
    db.session.commit()
    return tpl


def render_template_preview(tpl: ReportTemplate) -> dict[str, Any]:
    cfg = template_config(tpl)
    entity = cfg.get('entity')
    fields = cfg.get('fields') or []
    limit = int(cfg.get('limit') or 100)
    return run_entity_preview(entity, fields, limit)
