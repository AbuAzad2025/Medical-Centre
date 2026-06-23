"""User preferences API — phase 11."""
from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.shared.user_preferences import get_user_preferences, save_user_preferences

api_user_bp = Blueprint('api_user', __name__)


@api_user_bp.route('/preferences', methods=['GET', 'POST'])
@login_required
def user_preferences():
    if request.method == 'GET':
        return jsonify({'preferences': get_user_preferences(current_user)})

    data = request.get_json(silent=True) or {}
    updates = {}
    for key in ('theme', 'density', 'radius', 'dashboard'):
        if key in data:
            updates[key] = data[key]
    if not updates:
        return jsonify({'success': False, 'error': 'لا توجد حقول صالحة'}), 400
    if not save_user_preferences(current_user, updates):
        return jsonify({'success': False}), 500
    prefs = get_user_preferences(current_user)
    return jsonify({'success': True, 'preferences': prefs})
