"""Phase 3.2 - Lab API endpoints (cancel / amend) for thin JSON clients."""

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from utils.decorators import role_required_json

api_lab_bp = Blueprint('api_lab', __name__)

_API_ROLES = ('reception', 'super_admin', 'admin', 'doctor', 'nurse', 'lab', 'emergency')


@api_lab_bp.route('/requests/<int:request_id>/cancel', methods=['POST'])
@login_required
@role_required_json(*_API_ROLES)
def cancel_lab_request(request_id: int):
    from services.lab_service import LabService

    reason = request.get_json(silent=True).get('reason') if request.is_json else None
    ok, payload = LabService.cancel_request(request_id, cancelled_by=current_user.id, reason=reason)
    return jsonify(payload), (200 if ok else 400)


@api_lab_bp.route('/results/<int:result_id>/amend', methods=['POST'])
@login_required
@role_required_json(*_API_ROLES)
def amend_lab_result(result_id: int):
    from services.lab_service import LabService

    payload = request.get_json(silent=True) or {}
    ok, result = LabService.amend_result(
        result_id,
        value=payload.get('value'),
        unit=payload.get('unit'),
        notes=payload.get('notes'),
        is_critical=bool(payload.get('is_critical', False)),
        amended_by=current_user.id,
    )
    return jsonify(result), (200 if ok else 400)
