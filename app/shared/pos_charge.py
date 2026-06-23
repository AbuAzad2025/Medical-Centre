"""Shared POS terminal charge handler (reception + pharmacy)."""

from __future__ import annotations

import logging

from app.shared.user_messages import localize_pos_message, user_message
from services.pos_terminal_service import PosTerminalService


def execute_pos_charge(amount_raw) -> tuple[dict, int]:
    try:
        amount = float(amount_raw or 0)
        if amount <= 0:
            return {'success': False, 'message': user_message('pos_amount_invalid')}, 400
        result = PosTerminalService.charge(amount)
        if not result.get('success'):
            result = dict(result)
            result['message'] = localize_pos_message(result.get('message'))
            return result, 500
        return result, 200
    except (TypeError, ValueError):
        return {'success': False, 'message': user_message('pos_amount_invalid')}, 400
    except Exception:
        logging.exception('POS charge error')
        return {'success': False, 'message': user_message('pos_generic_error')}, 500
