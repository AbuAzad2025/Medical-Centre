"""User-facing Arabic messages — display layer only (§35.5)."""

from __future__ import annotations

USER_MESSAGES = {
    'pos_not_enabled': (
        'جهاز البطاقة غير مفعّل في هذا المركز. تواصل مع المدير أو اختر الدفع نقداً.'
    ),
    'pos_connection_failed': (
        'تعذّر الاتصال بجهاز البطاقة. تأكد أن الجهاز يعمل وحاول مرة أخرى.'
    ),
    'pos_charge_failed': (
        'لم تتم عملية البطاقة. يمكنك المحاولة مجدداً أو اختيار طريقة دفع أخرى.'
    ),
    'sale_failed': 'تعذّر إتمام البيع. راجع السلة وحاول مرة أخرى.',
    'pos_amount_invalid': 'قيمة المبلغ غير صحيحة',
    'pos_unauthorized': 'غير مصرح',
    'pos_generic_error': 'تعذر تنفيذ عملية الدفع حالياً',
}


def user_message(code: str, fallback: str = '') -> str:
    return USER_MESSAGES.get(code, fallback or code)


def localize_pos_message(raw: str | None) -> str:
    """Map technical POS backend text to friendly Arabic."""
    if not raw:
        return user_message('pos_charge_failed')
    lower = raw.lower()
    if 'not enabled' in lower:
        return user_message('pos_not_enabled')
    if '(conn)' in lower or 'اتصال بجهاز' in raw:
        return user_message('pos_connection_failed')
    if any(ar in raw for ar in ('تعذر', 'تعذّر', 'غير مفعل', 'غير مفعّل')):
        return raw
    return user_message('pos_charge_failed')
