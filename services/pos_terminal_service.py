import json
import os
from urllib import error, request


class PosTerminalService:
    @staticmethod
    def is_enabled() -> bool:
        # An operator who sets POS_ENABLED=false means it. OR-ing the flag with
        # "is a base URL configured" made the switch impossible to turn off:
        # a leftover base URL kept the terminal live.
        v = os.environ.get('POS_ENABLED', '').strip().lower()
        if v:
            return v in {'1', 'true', 'yes', 'on'}
        return bool(os.environ.get('POS_BASE_URL'))

    @staticmethod
    def base_url() -> str:
        # A variable that is set but empty is not a base URL. Returning it
        # verbatim built the relative URL '/charge'.
        return os.environ.get('POS_BASE_URL', '').strip() or 'http://127.0.0.1:9100/api/pos'

    @staticmethod
    def charge(amount: float, currency: str = 'ILS') -> dict:
        if not PosTerminalService.is_enabled():
            return {
                'success': False,
                # Stable machine-readable discriminator so callers can map this
                # to 503 (feature unavailable) instead of a generic 500.
                'code': 'pos_not_enabled',
                'message': 'خدمة الدفع الإلكتروني غير مفعلة حالياً (not enabled)',
            }
        try:
            payload = json.dumps({'amount': amount, 'currency': currency}).encode('utf-8')
            req = request.Request(
                url=f'{PosTerminalService.base_url().rstrip("/")}/charge',
                data=payload,
                headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
                method='POST',
            )
            with request.urlopen(req, timeout=15) as resp:
                data = resp.read().decode('utf-8')
                parsed = json.loads(data)
                succeeded = bool(parsed.get('success', True))
                result = {
                    'success': succeeded,
                    'transaction_id': parsed.get('transaction_id'),
                    'approval_code': parsed.get('approval_code'),
                    'card_last_digits': parsed.get('card_last_digits'),
                    'card_holder_name': parsed.get('card_holder_name'),
                    'amount': parsed.get('amount', amount),
                    'currency': parsed.get('currency', currency),
                    'message': parsed.get('message'),
                }
                if not succeeded:
                    # The terminal reached the issuer and the issuer refused.
                    # Without a code the caller cannot tell a decline from a
                    # terminal fault, and every decline was reported as a
                    # server error instead of 402.
                    result['code'] = 'pos_declined'
                return result
        except error.HTTPError as exc:
            return {
                'success': False,
                'code': 'pos_terminal_error',
                'status': exc.code,
                'message': 'تعذر تنفيذ عملية الدفع عبر الجهاز حالياً',
            }
        except error.URLError:
            return {
                'success': False,
                'code': 'pos_terminal_unreachable',
                'message': 'تعذر الاتصال بجهاز الدفع حالياً (conn)',
            }
        except Exception:
            return {
                'success': False,
                'code': 'pos_terminal_error',
                'message': 'تعذر تنفيذ عملية الدفع حالياً',
            }
