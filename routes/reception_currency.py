"""
Reception Currency API — حفظ سعر الصرف اليدوي من المودال
"""

import logging

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from services.currency_service import CurrencyConverter
from utils.decorators import role_required

reception_currency_bp = Blueprint('reception_currency', __name__)


@reception_currency_bp.route('/api/save-manual-rate', methods=['POST'])
@login_required
@role_required('manager', 'admin', 'super_admin')
def save_manual_rate():
    """O-U?O, O3O1O� O�O�U? USO_U^US U.U+ O,U,U^O_O,U,"""
    try:
        data = request.get_json(force=True, silent=True) or {}
        from_currency = data.get('from_currency', '').strip().upper()
        to_currency = data.get('to_currency', '').strip().upper()
        rate = data.get('rate')

        if not from_currency or not to_currency or rate is None:
            return jsonify({'success': False, 'error': 'O�U.USO1 O,U,O-U,U^U, U.O�U,U^O"Oc'}), 400

        # A rate has to be a positive number. A zero or negative rate is not a
        # conversion, and the money side of every foreign-currency payment
        # would be computed from it.
        try:
            rate_value = float(rate)
        except (TypeError, ValueError):
            return jsonify({'success': False, 'error': 'O�U.USO1 O,U,O-U,U^U, U.O�U,U^O"Oc'}), 400
        if not (rate_value > 0) or rate_value > 1_000_000:
            return jsonify({'success': False, 'error': 'O�U.USO1 O,U,O-U,U^U, U.O�U,U^O"Oc'}), 400

        rate = CurrencyConverter.ensure_manual_rate(
            from_currency=from_currency,
            to_currency=to_currency,
            sell_rate=rate_value,
            buy_rate=rate_value,
            user_id=current_user.id,
        )
        return jsonify(
            {
                'success': True,
                'message': f'تم حفظ سعر الصرف {from_currency} → {to_currency}',
                'rate_id': rate.id,
                'sell_rate': float(rate.sell_rate),
            }
        )
    except Exception:
        logging.exception('Error saving manual rate: %s')
        return jsonify({'success': False, 'error': 'تعذر حفظ سعر الصرف'}), 500


@reception_currency_bp.route('/api/check-rate', methods=['GET'])
@login_required
def check_rate():
    """التحقق مما إذا كان سعر الصرف متوفراً"""
    from_currency = request.args.get('from', 'ILS').upper()
    to_currency = request.args.get('to', 'USD').upper()
    rate = CurrencyConverter.get_rate(from_currency, to_currency)
    return jsonify(
        {
            'available': rate is not None,
            'rate': float(rate) if rate else None,
            'from_currency': from_currency,
            'to_currency': to_currency,
        }
    )
