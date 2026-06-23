"""User-facing Arabic messages — display layer only (§35.5 / §36.2)."""

from __future__ import annotations

import re

USER_MESSAGES: dict[str, str] = {
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
    'pos_unauthorized': 'غير مصرح لك بهذا الإجراء.',
    'pos_generic_error': 'تعذّر تنفيذ عملية الدفع حالياً. حاول بعد قليل.',
    'save_failed': 'تعذّر الحفظ. حاول مرة أخرى.',
    'delete_failed': 'تعذّر الحذف. حاول مرة أخرى.',
    'network_error': 'انقطع الاتصال. تحقق من الشبكة وحاول مرة أخرى.',
    'forbidden': 'ليس لديك صلاحية لهذا الإجراء.',
    'generic_error': 'حدث خطأ غير متوقع. حاول مرة أخرى أو تواصل مع الدعم.',
    'visit_summary_save_failed': 'تعذّر حفظ ملخص الزيارة. حاول مرة أخرى.',
    'notes_save_failed': 'تعذّر حفظ الملاحظة. حاول مرة أخرى.',
    'notes_delete_failed': 'تعذّر حذف القالب. حاول مرة أخرى.',
    'chart_save_failed': 'تعذّر حفظ مخطط الأسنان. حاول مرة أخرى.',
    'dashboard_load_failed': 'تعذّر تحميل إعدادات اللوحة. حاول تحديث الصفحة.',
}

_TECHNICAL_RE = re.compile(
    r'integrityerror|traceback|sqlalchemy|httperror|'
    r'\b403\b|\b500\b|\b404\b|payment_method|visit_id|medication_id|'
    r'not enabled|connection refused|networkerror',
    re.IGNORECASE,
)


def user_message(code: str, fallback: str = '') -> str:
    return USER_MESSAGES.get(code, fallback or code)


def resolve_user_message(value: str | None) -> str:
    """Map a code or raw backend/JS string to friendly Arabic for display."""
    if value is None:
        return ''
    text = str(value).strip()
    if not text:
        return ''
    if text in USER_MESSAGES:
        return USER_MESSAGES[text]
    if _TECHNICAL_RE.search(text):
        return user_message('generic_error')
    if text.lower().startswith('error') or text.startswith('خطأ:'):
        cleaned = re.sub(r'^(?:خطأ|Error)\s*:?\s*', '', text, flags=re.IGNORECASE).strip()
        if cleaned and not _TECHNICAL_RE.search(cleaned) and _looks_arabic(cleaned):
            return cleaned
        return user_message('generic_error')
    if _looks_arabic(text):
        return text
    return user_message('generic_error')


def _looks_arabic(text: str) -> bool:
    return any('\u0600' <= ch <= '\u06FF' for ch in text)


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
