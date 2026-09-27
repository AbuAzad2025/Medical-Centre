"""Shared POS terminal charge handler (reception + pharmacy)."""

from __future__ import annotations

import logging

from app.shared.user_messages import localize_pos_message, user_message
from services.pos_terminal_service import PosTerminalService

# Business/precondition failures are not server errors. Mapping every one of
# them to 500 made a correctly configured deployment with no card terminal look
# broken and buried real incidents in error dashboards. PosTerminalService now
# reports a stable `code`, and only that code is mapped; an unrecognised result
# keeps the historical 500.
_POS_STATUS_BY_CODE = {
    'pos_not_enabled': 503,  # feature not configured for this tenant
    'pos_terminal_unreachable': 503,  # device offline / DNS / refused
    'pos_terminal_error': 502,  # upstream terminal returned an error
    'pos_declined': 402,  # issuer declined the charge
}


def _status_for(result: dict) -> int:
    """Map a POS failure onto an HTTP status.

    Only an explicit ``code`` from PosTerminalService is trusted. Anything
    unrecognised — including a stubbed or legacy service that returns only
    ``success``/``message`` — keeps the previous 500 rather than being guessed
    at, so this helper never changes the contract for a response it cannot
    actually classify.
    """
    return _POS_STATUS_BY_CODE.get(result.get('code'), 500)


def execute_pos_charge(amount_raw) -> tuple[dict, int]:
    try:
        amount = float(amount_raw or 0)
        if amount <= 0:
            return {'success': False, 'message': user_message('pos_amount_invalid')}, 400
        result = PosTerminalService.charge(amount)
        if not result.get('success'):
            result = dict(result)
            result['message'] = localize_pos_message(result.get('message'))
            return result, _status_for(result)
        return result, 200
    except (TypeError, ValueError):
        return {'success': False, 'message': user_message('pos_amount_invalid')}, 400
    except Exception:
        logging.exception('POS charge error')
        return {'success': False, 'message': user_message('pos_generic_error')}, 500
