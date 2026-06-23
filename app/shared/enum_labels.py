"""Arabic labels for shared enums — Jinja ``enum_label`` filter."""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from app.shared import enums as enums_module

ENUM_LABELS_AR: dict[str, dict[str, str]] = {
    'VisitState': {
        'OPEN': 'مفتوح',
        'CHECKED_IN': 'حضور مسجّل',
        'IN_PROGRESS': 'قيد المعالجة',
        'COMPLETED': 'مكتمل',
        'ARCHIVED': 'مؤرشف',
        'CANCELLED': 'ملغى',
        'NO_SHOW': 'لم يحضر',
    },
    'VisitWorkflowStatus': {
        'REGISTERED': 'مسجّل',
        'WAITING': 'في الانتظار',
        'IN_PROGRESS': 'قيد المعالجة',
        'COMPLETED': 'مكتمل',
        'ARCHIVED': 'مؤرشف',
        'CANCELLED': 'ملغى',
    },
    'PaymentStatus': {
        'PENDING': 'قيد الانتظار',
        'PAID': 'مدفوع',
        'PARTIAL': 'دفع جزئي',
        'DEBT': 'دين',
        'EMERGENCY_DEBT': 'دين طوارئ',
        'CONFIRMED': 'مؤكّد',
        'REFUNDED': 'مسترد',
        'CANCELLED': 'ملغى',
    },
    'PaymentMethod': {
        'CASH': 'نقداً',
        'CARD': 'بطاقة',
        'VISA': 'فيزا',
        'MADA': 'مدى',
        'WIRE': 'تحويل',
        'INSURANCE': 'تأمين',
        'FORCE': 'إدخال قسري',
    },
    'AppointmentState': {
        'SCHEDULED': 'مجدول',
        'CONFIRMED': 'مؤكّد',
        'CHECKED_IN': 'حضور مسجّل',
        'DONE': 'منتهٍ',
        'COMPLETED': 'مكتمل',
        'CANCELLED': 'ملغى',
        'NO_SHOW': 'لم يحضر',
    },
    'TenantStatus': {
        'ACTIVE': 'نشط',
        'SUSPENDED': 'موقوف',
        'PENDING': 'قيد الانتظار',
        'TRIAL': 'تجريبي',
        'EXPIRED': 'منتهي',
        'CANCELLED': 'ملغى',
        'DELETED': 'محذوف',
    },
    'UserRole': {
        'owner': 'مالك المنصة',
        'super_admin': 'مدير المركز',
        'admin': 'مسؤول',
        'manager': 'مدير تشغيل',
        'reception': 'استقبال',
        'doctor': 'طبيب',
        'nurse': 'تمريض',
        'lab': 'مختبر',
        'radiology': 'أشعة',
        'pharmacy': 'صيدلية',
        'accountant': 'محاسبة',
        'patient': 'مريض',
        'emergency': 'طوارئ',
    },
    'QueueState': {
        'WAITING': 'في الانتظار',
        'CALLED': 'تم الاستدعاء',
        'IN_PROGRESS': 'قيد المعالجة',
        'COMPLETED': 'مكتمل',
        'SKIPPED': 'تم التخطي',
        'CANCELLED': 'ملغى',
        'waiting': 'في الانتظار',
        'called': 'تم الاستدعاء',
        'in_progress': 'قيد المعالجة',
        'completed': 'مكتمل',
        'skipped': 'تم التخطي',
        'cancelled': 'ملغى',
    },
    'InvoiceStatus': {
        'DRAFT': 'مسودة',
        'ISSUED': 'صادرة',
        'POSTED': 'مرحّلة',
        'PAID': 'مدفوعة',
        'VOID': 'ملغاة',
    },
    'OrderState': {
        'REQUESTED': 'مطلوب',
        'RECEIVED': 'مستلم',
        'ANALYZING': 'قيد التحليل',
        'REVIEWED': 'تمت المراجعة',
        'APPROVED': 'معتمد',
        'IN_PROGRESS': 'قيد التنفيذ',
        'DONE': 'منتهٍ',
        'CANCELLED': 'ملغى',
    },
    'PrescriptionState': {
        'DRAFT': 'مسودة',
        'ACTIVE': 'نشطة',
        'DISPENSED': 'صُرفت',
        'PARTIAL': 'صرف جزئي',
        'CANCELLED': 'ملغاة',
        'EXPIRED': 'منتهية',
        'draft': 'مسودة',
        'active': 'نشطة',
        'dispensed': 'صُرفت',
        'partial': 'صرف جزئي',
        'cancelled': 'ملغاة',
        'expired': 'منتهية',
    },
    'BillingState': {
        'PENDING': 'قيد الانتظار',
        'PAID': 'مدفوع',
        'PARTIAL': 'دفع جزئي',
        'DEBT': 'دين',
        'CANCELLED': 'ملغى',
        'REFUNDED': 'مسترد',
    },
}


def _member_key(value: Any) -> str:
    if isinstance(value, Enum):
        return value.name
    return str(value).strip()


def _lookup_label(enum_name: str, member_key: str) -> Optional[str]:
    table = ENUM_LABELS_AR.get(enum_name, {})
    if member_key in table:
        return table[member_key]
    upper = member_key.upper()
    if upper in table:
        return table[upper]
    lower = member_key.lower()
    if lower in table:
        return table[lower]
    return None


def enum_label(value: Any, enum_name: str = '') -> str:
    """Jinja filter: ``{{ visit.status | enum_label('VisitState') }}``."""
    if value is None or value == '':
        return ''
    key = _member_key(value)

    if enum_name:
        label = _lookup_label(enum_name, key)
        if label:
            return label
        enum_cls = getattr(enums_module, enum_name, None)
        if isinstance(enum_cls, type) and issubclass(enum_cls, Enum):
            try:
                member = enum_cls(key)
                if hasattr(member, 'label_ar'):
                    return member.label_ar
            except (ValueError, KeyError):
                try:
                    member = enum_cls(key.lower())
                    if hasattr(member, 'label_ar'):
                        return member.label_ar
                except (ValueError, KeyError):
                    pass

    for table in ENUM_LABELS_AR.values():
        if key in table:
            return table[key]
        if key.upper() in table:
            return table[key.upper()]
        if key.lower() in table:
            return table[key.lower()]

    return key.replace('_', ' ')


def resolve_visit_payment_status_badge(
    status: Any,
    paid_amount: Any = 0,
    remaining_amount: Any = None,
) -> dict[str, str]:
    """Bootstrap variant + Arabic label for visit payment status (G-120)."""
    paid = float(paid_amount or 0)
    rem = float(remaining_amount if remaining_amount is not None else 1)
    key = _member_key(status) if status else ''

    if key == 'PAID' or rem <= 0:
        label = _lookup_label('PaymentStatus', 'PAID') or 'مدفوع'
        return {'variant': 'success', 'label': label}

    if key == 'PARTIAL' or (paid > 0 and rem > 0):
        return {
            'variant': 'info',
            'label': enum_label('PARTIAL', 'PaymentStatus'),
        }

    variant_by_status = {
        'PENDING': 'warning',
        'DEBT': 'danger',
        'EMERGENCY_DEBT': 'danger',
        'REFUNDED': 'secondary',
        'CANCELLED': 'secondary',
        'CONFIRMED': 'info',
    }
    variant = variant_by_status.get(key.upper(), 'secondary')
    label = enum_label(status, 'PaymentStatus') or key
    return {'variant': variant, 'label': label}
