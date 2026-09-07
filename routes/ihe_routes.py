"""
IHE PIX/PDQ + ATNA routes — ITI-8/9/21
"""

from flask import Blueprint, g, jsonify, request
from flask_login import login_required

from services.ihe_pix_pdq_service import ihe_service
from utils.api_security import limit_payload_size
from utils.decorators import role_required

ihe_bp = Blueprint('ihe', __name__)


def _tenant_id():
    return getattr(g, 'tenant_id', None)


@ihe_bp.route('/pix/query', methods=['GET'])
@login_required
@role_required('doctor', 'nurse', 'admin', 'manager', 'super_admin', 'reception')
@limit_payload_size(64 * 1024)
def pix_query():
    pid = request.args.get('patient_id') or request.args.get('id') or ""
    domain = request.args.get('domain')
    if not pid:
        return jsonify(success=False, error='patient_id required'), 400
    result = ihe_service.pix_query(pid, domain=domain, tenant_id=_tenant_id())
    ihe_service.atna_audit("PIX Query", getattr(g, 'user_id', None), None, "0" if result.get("found") else "4")
    return jsonify(result)


@ihe_bp.route('/pdq/query', methods=['GET'])
@login_required
@role_required('doctor', 'nurse', 'admin', 'manager', 'super_admin', 'reception')
@limit_payload_size(64 * 1024)
def pdq_query():
    result = ihe_service.pdq_query(
        family_name=request.args.get('family'),
        given_name=request.args.get('given'),
        birth_date=request.args.get('birthDate'),
        phone=request.args.get('phone'),
        tenant_id=_tenant_id(),
        limit=min(int(request.args.get('limit', 20)), 50),
    )
    return jsonify(result)


@ihe_bp.route('/atna/audit', methods=['POST'])
@login_required
@role_required('super_admin', 'admin')
@limit_payload_size(64 * 1024)
def atna_audit():
    data = request.get_json(silent=True) or {}
    ihe_service.atna_audit(
        data.get('event_type', 'IHE'),
        data.get('user_id'),
        data.get('patient_id'),
        data.get('outcome', '0'),
    )
    return jsonify(success=True)
