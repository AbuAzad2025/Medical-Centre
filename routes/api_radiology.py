"""Phase 3.2 - Radiology API endpoints (cancel / amend) for thin JSON clients."""

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from utils.decorators import role_required_json

api_radiology_bp = Blueprint('api_radiology', __name__)

_API_ROLES = (
    'reception',
    'super_admin',
    'admin',
    'doctor',
    'nurse',
    'radiology',
    'emergency',
)


@api_radiology_bp.route('/requests/<int:request_id>/cancel', methods=['POST'])
@login_required
@role_required_json(*_API_ROLES)
def cancel_radiology_request(request_id: int):
    from services.radiology_service import RadiologyService

    reason = request.get_json(silent=True).get('reason') if request.is_json else None
    ok, payload = RadiologyService.cancel_request(
        request_id, cancelled_by=current_user.id, reason=reason
    )
    return jsonify(payload), (200 if ok else 400)


@api_radiology_bp.route('/results/<int:result_id>/amend', methods=['POST'])
@login_required
@role_required_json(*_API_ROLES)
def amend_radiology_result(result_id: int):
    from services.radiology_service import RadiologyService

    payload = request.get_json(silent=True) or {}
    ok, result = RadiologyService.amend_result(
        result_id,
        findings=payload.get('findings'),
        impression=payload.get('impression'),
        is_critical=bool(payload.get('is_critical', False)),
        amended_by=current_user.id,
    )
    return jsonify(result), (200 if ok else 400)
