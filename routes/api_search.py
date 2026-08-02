"""Unified search API routes (G-84)."""

from flask import Blueprint, jsonify, request
from flask_login import login_required

from utils.decorators import role_required_json

api_search_bp = Blueprint('api_search', __name__)

_ALLOWED_PATIENT_ROLES = frozenset(
    {
        'reception',
        'super_admin',
        'admin',
        'manager',
        'doctor',
        'nurse',
        'emergency',
    }
)


@api_search_bp.route('/patients')
@login_required
@role_required_json('reception', 'super_admin', 'admin', 'manager', 'doctor', 'nurse', 'emergency')
def search_patients():
    from app.shared.search_service import SearchService

    q = request.args.get('q', '').strip()
    limit = request.args.get('limit', 20, type=int)
    patients = SearchService.search_patients(q, limit=limit)
    return jsonify({'patients': patients, 'count': len(patients)})
