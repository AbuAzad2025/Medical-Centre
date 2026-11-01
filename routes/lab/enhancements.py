import logging
from datetime import UTC, datetime

from flask import g, jsonify, request
from flask_login import login_required
from sqlalchemy import select

from app.extensions import db
from models.lab_request import LabResult
from routes.lab import lab_bp
from utils.decorators import role_required

_RESULT_TEMPLATES: list = []
_TEMPLATE_COUNTER = 0
_RESULT_HISTORY: dict = {}


def _next_template_id() -> int:
    global _TEMPLATE_COUNTER
    _TEMPLATE_COUNTER += 1
    return _TEMPLATE_COUNTER


def _to_float(value):
    if value is None:
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


@lab_bp.route('/result-templates', methods=['GET', 'POST'])
@lab_bp.route('/templates', methods=['GET', 'POST'])
@lab_bp.route('/api/result-templates', methods=['GET', 'POST'])
@login_required
@role_required('lab', 'admin', 'manager', 'doctor')
def result_templates():
    tenant_id = getattr(g, 'tenant_id', None)
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        if not data and request.form:
            data = request.form.to_dict()
        template = {
            'id': _next_template_id(),
            'tenant_id': tenant_id,
            'name': data.get('name') or data.get('template_name'),
            'test_code': data.get('test_code'),
            'test_name': data.get('test_name'),
            'default_unit': data.get('unit') or data.get('default_unit'),
            'reference_range': data.get('reference_range'),
            'formula': data.get('formula'),
            'created_at': datetime.now(UTC).isoformat(),
        }
        _RESULT_TEMPLATES.append(template)
        return jsonify({'success': True, 'data': template}), 201
    out = [t for t in _RESULT_TEMPLATES if t.get('tenant_id') == tenant_id]
    return jsonify({'success': True, 'templates': out, 'count': len(out)})


@lab_bp.route('/result-templates/<int:template_id>', methods=['GET', 'DELETE'])
@login_required
@role_required('lab', 'admin', 'manager', 'doctor')
def result_template_detail(template_id: int):
    for i, t in enumerate(_RESULT_TEMPLATES):
        if t.get('id') == template_id:
            if request.method == 'DELETE':
                _RESULT_TEMPLATES.pop(i)
                return jsonify({'success': True})
            return jsonify({'success': True, 'data': t})
    return jsonify({'success': False, 'error': 'Template not found'}), 404


@lab_bp.route('/calculate', methods=['POST', 'GET'])
@lab_bp.route('/derived-values', methods=['POST', 'GET'])
@lab_bp.route('/api/derived-values', methods=['POST', 'GET'])
@lab_bp.route('/auto-calculate', methods=['POST', 'GET'])
@login_required
@role_required('lab', 'admin', 'manager', 'doctor')
def derived_values():
    data = request.get_json(silent=True) or {}
    if not data and request.args:
        data = request.args.to_dict()
    formula = (data.get('formula') or '').strip().lower()
    values = data.get('values') or {}
    try:
        if isinstance(values, str):
            import json

            values = json.loads(values)
    except Exception:
        values = {}
    result = None
    try:
        if formula == 'bmi':
            weight = _to_float(values.get('weight'))
            height = _to_float(values.get('height'))
            if weight and height:
                result = weight / ((height / 100.0) ** 2)
        elif formula == 'egfr':
            # simplified placeholder
            creatinine = _to_float(values.get('creatinine'))
            age = _to_float(values.get('age'))
            if creatinine and age:
                result = 141 * min(creatinine / 0.9, 1) ** -0.411 * max(creatinine / 0.9, 1) ** -1.209 * 0.993 ** age
        elif formula == 'ratio':
            a = _to_float(values.get('a'))
            b = _to_float(values.get('b'))
            if a is not None and b not in (None, 0):
                result = a / b
        elif formula == 'sum':
            result = sum(_to_float(v) or 0 for v in (values.values() if isinstance(values, dict) else []))
        elif formula == 'difference':
            nums = [_to_float(v) for v in (values.values() if isinstance(values, dict) else [])]
            nums = [n for n in nums if n is not None]
            if len(nums) >= 2:
                result = nums[0] - nums[1]
        elif formula:
            # safe eval of arithmetic using only numbers and basic ops
            import ast
            import operator

            allowed = {
                ast.Add: operator.add,
                ast.Sub: operator.sub,
                ast.Mult: operator.mul,
                ast.Div: operator.truediv,
                ast.Pow: operator.pow,
                ast.USub: operator.neg,
            }
            node = ast.parse(formula, mode='eval').body

            def _eval(n):
                if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
                    return n.value
                if isinstance(n, ast.BinOp) and type(n.op) in allowed:
                    return allowed[type(n.op)](_eval(n.left), _eval(n.right))
                if isinstance(n, ast.UnaryOp) and type(n.op) in allowed:
                    return allowed[type(n.op)](_eval(n.operand))
                # variable lookup from values
                if isinstance(n, ast.Name):
                    v = _to_float(values.get(n.id))
                    if v is None:
                        raise ValueError('unknown variable')
                    return v
                raise ValueError('unsupported expression')

            result = _eval(node)
    except Exception:
        logging.exception('Error calculating derived value')
        return jsonify({'success': False, 'error': 'Calculation failed'}), 400
    return jsonify({'success': True, 'formula': formula, 'result': result})


@lab_bp.route('/critical-alerts', methods=['GET'])
@lab_bp.route('/critical-values', methods=['GET'])
@lab_bp.route('/api/critical-alerts', methods=['GET'])
@lab_bp.route('/api/critical-values', methods=['GET'])
@login_required
@role_required('lab', 'admin', 'manager', 'doctor')
def critical_value_alerts():
    tenant_id = getattr(g, 'tenant_id', None)
    try:
        q = select(LabResult).filter(LabResult.is_critical.is_(True))
        if tenant_id is not None:
            q = q.filter(LabResult.tenant_id == tenant_id)
        items = db.session.execute(q.order_by(LabResult.created_at.desc()).limit(100)).scalars().all()
        out = []
        for r in items:
            out.append(
                {
                    'id': r.id,
                    'request_id': r.request_id,
                    'patient_id': r.patient_id,
                    'test_code': r.test_code,
                    'test_name': r.test_name,
                    'value': r.value,
                    'unit': r.unit,
                    'reference_range': r.reference_range,
                    'is_critical': r.is_critical,
                    'status': r.status,
                    'created_at': r.created_at.isoformat() if r.created_at else None,
                }
            )
        return jsonify({'success': True, 'alerts': out, 'count': len(out)})
    except Exception:
        logging.exception('Error loading critical value alerts')
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@lab_bp.route('/results/<int:result_id>/history', methods=['GET'])
@lab_bp.route('/result-history/<int:result_id>', methods=['GET'])
@lab_bp.route('/api/results/<int:result_id>/history', methods=['GET'])
@login_required
@role_required('lab', 'admin', 'manager', 'doctor')
def result_history(result_id: int):
    tenant_id = getattr(g, 'tenant_id', None)
    try:
        result = db.session.get(LabResult, result_id)
        if result is None or (tenant_id is not None and getattr(result, 'tenant_id', None) != tenant_id):
            return jsonify({'success': False, 'error': 'Result not found'}), 404
        history = _RESULT_HISTORY.get(result_id, [])
        # seed with current result if empty
        if not history:
            history = [
                {
                    'value': result.value,
                    'status': result.status,
                    'recorded_at': result.updated_at.isoformat() if result.updated_at else None,
                }
            ]
            _RESULT_HISTORY[result_id] = history
        return jsonify({'success': True, 'result_id': result_id, 'history': history, 'count': len(history)})
    except Exception:
        logging.exception('Error loading result history')
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@lab_bp.route('/results/<int:result_id>/history', methods=['POST'])
@login_required
@role_required('lab', 'admin', 'manager', 'doctor')
def append_result_history(result_id: int):
    tenant_id = getattr(g, 'tenant_id', None)
    try:
        result = db.session.get(LabResult, result_id)
        if result is None or (tenant_id is not None and getattr(result, 'tenant_id', None) != tenant_id):
            return jsonify({'success': False, 'error': 'Result not found'}), 404
        data = request.get_json(silent=True) or {}
        entry = {
            'value': data.get('value', result.value),
            'status': data.get('status', result.status),
            'notes': data.get('notes'),
            'recorded_at': datetime.now(UTC).isoformat(),
        }
        _RESULT_HISTORY.setdefault(result_id, []).append(entry)
        return jsonify({'success': True, 'data': entry}), 201
    except Exception:
        logging.exception('Error appending result history')
        return jsonify({'success': False, 'error': 'Internal server error'}), 500
