"""Kiosk routes — public self check-in."""
from flask import Blueprint, jsonify, render_template, request

from app.extensions import csrf
from services.kiosk_checkin_service import perform_kiosk_checkin

kiosk_bp = Blueprint('kiosk', __name__)


@kiosk_bp.route('/check-in')
def check_in():
    return render_template('kiosk/check_in.html')


@kiosk_bp.route('/api/check-in', methods=['POST'])
@csrf.exempt
def api_check_in():
    data = request.get_json(silent=True) or {}
    national_id = data.get('national_id') or request.form.get('national_id') or ''
    result = perform_kiosk_checkin(national_id)
    status = 200 if result.get('success') else 400
    if result.get('success') is False and 'لم يتم العثور' in result.get('message', ''):
        status = 404
    return jsonify(result), status
