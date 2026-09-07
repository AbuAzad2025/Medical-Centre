"""
Insurance Claims API — minimal CRUD for claim lifecycle (Phase 3)
"""

from flask import Blueprint, g, jsonify, request
from flask_login import login_required

from services.insurance_claim_service import InsuranceClaimService
from utils.api_security import limit_payload_size
from utils.decorators import role_required

insurance_bp = Blueprint('insurance', __name__)


def _tid():
    return getattr(g, 'tenant_id', None)


@insurance_bp.route('/api/claims', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor', 'accountant', 'super_admin')
@limit_payload_size(64 * 1024)
def list_claims():
    claims = InsuranceClaimService.list_claims(_tid())
    return jsonify({'claims': claims})


@insurance_bp.route('/api/claims', methods=['POST'])
@login_required
@role_required('admin', 'manager', 'doctor', 'accountant', 'super_admin')
@limit_payload_size(64 * 1024)
def create_claim():
    data = request.get_json(silent=True) or {}
    ok, payload = InsuranceClaimService.create_claim(
        visit_id=data.get('visit_id'),
        invoice_id=data.get('invoice_id'),
        company_id=data.get('company_id'),
        total_claim=data.get('total_claim', 0),
        tenant_id=_tid(),
    )
    return jsonify(payload), (201 if ok else 400)


@insurance_bp.route('/api/claims/<int:claim_id>/submit', methods=['POST'])
@login_required
@role_required('admin', 'manager', 'accountant', 'super_admin')
@limit_payload_size(64 * 1024)
def submit_claim(claim_id):
    ok, payload = InsuranceClaimService.submit_claim(claim_id, _tid())
    return jsonify(payload), (200 if ok else 400)


@insurance_bp.route('/api/claims/<int:claim_id>/adjudicate', methods=['POST'])
@login_required
@role_required('admin', 'manager', 'accountant', 'super_admin')
@limit_payload_size(64 * 1024)
def adjudicate_claim(claim_id):
    data = request.get_json(silent=True) or {}
    ok, payload = InsuranceClaimService.adjudicate_claim(
        claim_id,
        approved_amount=data.get('approved_amount'),
        status=data.get('status'),
        notes=data.get('notes'),
        tenant_id=_tid(),
    )
    return jsonify(payload), (200 if ok else 400)


@insurance_bp.route('/api/claims/<int:claim_id>/settle', methods=['POST'])
@login_required
@role_required('admin', 'manager', 'accountant', 'super_admin')
@limit_payload_size(64 * 1024)
def settle_claim(claim_id):
    data = request.get_json(silent=True) or {}
    ok, payload = InsuranceClaimService.settle_claim(
        claim_id, settled_amount=data.get('settled_amount'), tenant_id=_tid()
    )
    return jsonify(payload), (200 if ok else 400)


@insurance_bp.route('/api/claims/<int:claim_id>/payout', methods=['POST'])
@login_required
@role_required('admin', 'manager', 'accountant', 'super_admin')
@limit_payload_size(64 * 1024)
def payout_claim(claim_id):
    data = request.get_json(silent=True) or {}
    ok, payload = InsuranceClaimService.record_payout(
        claim_id,
        amount=data.get('amount', 0),
        method=data.get('method', 'WIRE'),
        reference=data.get('reference'),
        tenant_id=_tid(),
    )
    return jsonify(payload), (200 if ok else 400)
