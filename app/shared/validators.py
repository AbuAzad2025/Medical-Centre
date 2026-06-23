"""Shared field validation rules — server + client (G-83)."""
from __future__ import annotations

import json
import re
from typing import Any

FIELD_RULES: dict[str, dict[str, Any]] = {
    'national_id': {
        'pattern': r'^\d{9}$',
        'message_ar': 'رقم الهوية يجب أن يكون 9 أرقام',
    },
    'phone': {
        'pattern': r'^(\+?970|0)?5\d{8}$',
        'message_ar': 'رقم جوال غير صالح (مثال: 0599123456)',
    },
    'email': {
        'pattern': r'^[^\s@]+@[^\s@]+\.[^\s@]+$',
        'message_ar': 'بريد إلكتروني غير صالح',
    },
    'amount': {
        'pattern': r'^\d+(\.\d{1,2})?$',
        'message_ar': 'المبلغ يجب أن يكون رقماً موجباً',
    },
    'patient_name': {
        'min_length': 2,
        'max_length': 120,
        'message_ar': 'الاسم قصير جداً',
    },
}

_COMPILED = {k: re.compile(v['pattern']) for k, v in FIELD_RULES.items() if v.get('pattern')}


def validate_field(rule_key: str, value: str | None) -> tuple[bool, str | None]:
    """Return (ok, message_ar). Empty optional values pass."""
    rules = FIELD_RULES.get(rule_key)
    if not rules:
        return True, None
    raw = (value or '').strip()
    if not raw:
        return True, None

    if 'min_length' in rules and len(raw) < rules['min_length']:
        return False, rules['message_ar']
    if 'max_length' in rules and len(raw) > rules['max_length']:
        return False, rules['message_ar']

    pat = _COMPILED.get(rule_key)
    if pat and not pat.match(raw):
        return False, rules['message_ar']
    return True, None


def get_rules_json() -> dict[str, Any]:
    return FIELD_RULES


def get_rules_json_str() -> str:
    return json.dumps(FIELD_RULES, ensure_ascii=False)
