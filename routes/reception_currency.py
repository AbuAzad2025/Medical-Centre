"""
Reception Currency API — حفظ سعر الصرف اليدوي من المودال
"""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from services.currency_service import CurrencyConverter
from app_factory import db
import logging

reception_currency_bp = Blueprint('reception_currency', __name__)


@reception_currency_bp.route('/api/save-manual-rate', methods=['POST'])
@login_required
def save_manual_rate():
    """حفظ سعر صرف يدوي من المودال"""
    try:
        data = request.get_json(force=True)
        from_currency = data.get('from_currency', '').strip().upper()
        to_currency = data.get('to_currency', '').strip().upper()
        rate = data.get('rate')

        if not from_currency or not to_currency or rate is None:
            return jsonify({'success': False, 'error': 'جميع الحقول مطلوبة'}), 400

        rate = CurrencyConverter.ensure_manual_rate(
            from_currency=from_currency,
            to_currency=to_currency,
            sell_rate=float(rate),
            buy_rate=float(rate),
            user_id=current_user.id,
        )
        return jsonify({
            'success': True,
            'message': f'تم حفظ سعر الصرف {from_currency} → {to_currency}',
            'rate_id': rate.id,
            'sell_rate': float(rate.sell_rate)
        })
    except Exception as e:
        logging.error(f"Error saving manual rate: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@reception_currency_bp.route('/api/check-rate', methods=['GET'])
@login_required
def check_rate():
    """التحقق مما إذا كان سعر الصرف متوفراً"""
    from_currency = request.args.get('from', 'ILS').upper()
    to_currency = request.args.get('to', 'USD').upper()
    rate = CurrencyConverter.get_rate(from_currency, to_currency)
    return jsonify({
        'available': rate is not None,
        'rate': float(rate) if rate else None,
        'from_currency': from_currency,
        'to_currency': to_currency,
    })
