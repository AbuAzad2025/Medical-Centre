import os
import json
from urllib import request, error


class PosTerminalService:
    @staticmethod
    def is_enabled() -> bool:
        v = os.environ.get('POS_ENABLED', '').strip().lower()
        return v in {'1', 'true', 'yes', 'on'} or bool(os.environ.get('POS_BASE_URL'))

    @staticmethod
    def base_url() -> str:
        return os.environ.get('POS_BASE_URL', 'http://127.0.0.1:9100/api/pos')

    @staticmethod
    def charge(amount: float, currency: str = 'ILS') -> dict:
        if not PosTerminalService.is_enabled():
            return {
                'success': False,
                'message': 'خدمة الدفع الإلكتروني غير مفعلة حالياً (not enabled)'
            }
        try:
            payload = json.dumps({'amount': amount, 'currency': currency}).encode('utf-8')
            req = request.Request(
                url=f"{PosTerminalService.base_url().rstrip('/')}/charge",
                data=payload,
                headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
                method='POST'
            )
            with request.urlopen(req, timeout=15) as resp:
                data = resp.read().decode('utf-8')
                parsed = json.loads(data)
                return {
                    'success': bool(parsed.get('success', True)),
                    'transaction_id': parsed.get('transaction_id'),
                    'approval_code': parsed.get('approval_code'),
                    'card_last_digits': parsed.get('card_last_digits'),
                    'card_holder_name': parsed.get('card_holder_name'),
                    'amount': parsed.get('amount', amount),
                    'currency': parsed.get('currency', currency),
                    'message': parsed.get('message')
                }
        except error.HTTPError as e:
            return {'success': False, 'message': 'تعذر تنفيذ عملية الدفع عبر الجهاز حالياً'}
        except error.URLError as e:
            return {'success': False, 'message': 'تعذر الاتصال بجهاز الدفع حالياً (conn)'}
        except Exception as e:
            return {'success': False, 'message': 'تعذر تنفيذ عملية الدفع حالياً'}
