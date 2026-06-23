"""Pure-logic tests for models/unified_mixins.py.

LEAN: no DB, no app context. Concrete dummy classes expose the mixin methods
and instance attributes are set directly, so every case is sub-millisecond.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from models.unified_mixins import (
    BaseModelMixin,
    StatusMixin,
    PermissionBase,
    FinancialBase,
    FileBase,
    NotificationBase,
)


# ---------------------------------------------------------------------------
# Dummy concrete classes — bypass SQLAlchemy mapping, exercise pure methods.
# ---------------------------------------------------------------------------
class _Col:
    def __init__(self, name):
        self.name = name


class _Table:
    def __init__(self, names):
        self.columns = [_Col(n) for n in names]


class DummyBase(BaseModelMixin):
    def __init__(self, **attrs):
        self.__dict__.update(attrs)


class DummyStatus(StatusMixin):
    def __init__(self, status):
        self.status = status


class DummyPermission(PermissionBase):
    def __init__(self, expires_at):
        self.expires_at = expires_at


class DummyFinancial(FinancialBase):
    def __init__(self, amount=None, currency='EGP', payment_status='PENDING'):
        self.amount = amount
        self.currency = currency
        self.payment_status = payment_status


class DummyFile(FileBase):
    def __init__(self, file_size):
        self.file_size = file_size


class DummyNotification(NotificationBase):
    def __init__(self, priority):
        self.priority = priority


# ---------------------------------------------------------------------------
# BaseModelMixin.to_dict
# ---------------------------------------------------------------------------
class TestToDict:
    def test_datetime_columns_serialized_to_iso(self):
        dt = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        obj = DummyBase(id=1, created_at=dt, name='x')
        obj.__table__ = _Table(['id', 'created_at', 'name'])
        result = obj.to_dict()
        assert result['id'] == 1
        assert result['created_at'] == dt.isoformat()
        assert result['name'] == 'x'

    def test_none_values_passthrough(self):
        obj = DummyBase(id=None, note=None)
        obj.__table__ = _Table(['id', 'note'])
        assert obj.to_dict() == {'id': None, 'note': None}

    def test_empty_columns_returns_empty_dict(self):
        obj = DummyBase()
        obj.__table__ = _Table([])
        assert obj.to_dict() == {}


# ---------------------------------------------------------------------------
# StatusMixin
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("status,display,color", [
    ('ACTIVE', 'نشط', 'success'),
    ('INACTIVE', 'غير نشط', 'secondary'),
    ('PENDING', 'في الانتظار', 'warning'),
    ('COMPLETED', 'مكتمل', 'success'),
    ('CANCELLED', 'ملغي', 'danger'),
    ('IN_PROGRESS', 'قيد التنفيذ', 'info'),
    ('READY', 'جاهز', 'primary'),
    ('ARCHIVED', 'مؤرشف', 'dark'),
])
def test_status_display_and_color(status, display, color):
    s = DummyStatus(status)
    assert s.get_status_display() == display
    assert s.get_status_color() == color


def test_status_unknown_falls_back_to_raw_value_and_secondary():
    s = DummyStatus('WEIRD_STATE')
    assert s.get_status_display() == 'WEIRD_STATE'
    assert s.get_status_color() == 'secondary'


@pytest.mark.parametrize("status,active,completed", [
    ('ACTIVE', True, False),
    ('COMPLETED', False, True),
    ('PENDING', False, False),
    ('CANCELLED', False, False),
])
def test_status_predicates(status, active, completed):
    s = DummyStatus(status)
    assert s.is_active() is active
    assert s.is_completed() is completed


# ---------------------------------------------------------------------------
# PermissionBase.is_expired
# ---------------------------------------------------------------------------
class TestPermissionExpiry:
    def test_none_expiry_never_expired(self):
        assert DummyPermission(None).is_expired() is False

    def test_past_expiry_is_expired(self):
        past = datetime.now(timezone.utc) - timedelta(days=1)
        assert DummyPermission(past).is_expired() is True

    def test_future_expiry_not_expired(self):
        future = datetime.now(timezone.utc) + timedelta(days=1)
        assert DummyPermission(future).is_expired() is False


# ---------------------------------------------------------------------------
# FinancialBase
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("amount,currency,expected", [
    (100, 'EGP', '100 EGP'),
    (0, 'USD', '0 USD'),
    ('250.50', 'ILS', '250.50 ILS'),
])
def test_amount_display(amount, currency, expected):
    f = DummyFinancial(amount=amount, currency=currency)
    assert f.get_amount_display() == expected


@pytest.mark.parametrize("status,paid,pending", [
    ('PAID', True, False),
    ('PENDING', False, True),
    ('PARTIAL', False, False),
    ('REFUNDED', False, False),
])
def test_financial_status_predicates(status, paid, pending):
    f = DummyFinancial(payment_status=status)
    assert f.is_paid() is paid
    assert f.is_pending() is pending


# ---------------------------------------------------------------------------
# FileBase.get_size_display — unit boundary sweep
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("size,expected", [
    (0, '0.0 B'),
    (1, '1.0 B'),
    (1023, '1023.0 B'),
    (1024, '1.0 KB'),
    (1536, '1.5 KB'),
    (1024 * 1024, '1.0 MB'),
    (1024 * 1024 * 1024, '1.0 GB'),
    (1024 ** 4, '1.0 TB'),
    (5 * 1024 ** 4, '5.0 TB'),
])
def test_file_size_display(size, expected):
    assert DummyFile(size).get_size_display() == expected


# ---------------------------------------------------------------------------
# NotificationBase.get_priority_color
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("priority,color", [
    ('LOW', 'secondary'),
    ('NORMAL', 'primary'),
    ('HIGH', 'warning'),
    ('URGENT', 'danger'),
    ('UNKNOWN', 'primary'),
])
def test_priority_color(priority, color):
    assert DummyNotification(priority).get_priority_color() == color
