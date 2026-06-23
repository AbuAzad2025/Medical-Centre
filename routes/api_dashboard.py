"""Dashboard live API — Command Center §29.5."""
from flask import Blueprint, jsonify
from flask_login import current_user, login_required

from app.shared.dashboard_service import snapshot_metrics

api_dashboard_bp = Blueprint('api_dashboard', __name__)


@api_dashboard_bp.route('/snapshot')
@login_required
def dashboard_snapshot():
    """Poll-friendly metrics for [data-widget-id] cards."""
    try:
        return jsonify(snapshot_metrics(current_user))
    except Exception as e:
        return jsonify({'error': str(e), 'metrics': {}}), 500
