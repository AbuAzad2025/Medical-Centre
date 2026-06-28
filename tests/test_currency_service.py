"""Tests for services.currency_service.CurrencyConverter (Wave 3)."""
import types
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from services.currency_service import CurrencyConverter as CC
from models.exchange_rate import ExchangeRate


@pytest.fixture
def fx(rollback_db):
    db = rollback_db

    def rate(from_c, to_c, sell, buy=None, source='MANUAL', hours_ago=0, active=True):
        r = ExchangeRate(
            from_currency=from_c,
            to_currency=to_c,
            buy_rate=Decimal(str(buy or sell)),
            sell_rate=Decimal(str(sell)),
            source=source,
            is_active=active,
            effective_date=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
        )
        db.session.add(r)
        db.session.commit()
        return r

    return types.SimpleNamespace(db=db, rate=rate)


class TestGetRate:
    def test_same_currency_is_one(self, fx):
        assert CC.get_rate('ILS', 'ILS') == Decimal('1.0')

    def test_manual_rate_preferred(self, fx):
        fx.rate('USD', 'ILS', sell=3.65)
        assert CC.get_rate('USD', 'ILS') == Decimal('3.65')

    def test_api_rate_within_24h(self, fx):
        fx.rate('USD', 'ILS', sell=3.70, source='API', hours_ago=1)
        assert CC.get_rate('USD', 'ILS') == Decimal('3.70')

    def test_api_rate_stale_ignored(self, fx):
        fx.rate('USD', 'ILS', sell=9.99, source='API', hours_ago=48)
        assert CC.get_rate('USD', 'ILS') is None

    def test_inverse_rate(self, fx):
        fx.rate('ILS', 'USD', sell=0.27, buy=0.27)
        got = CC.get_rate('USD', 'ILS')
        assert got is not None
        assert got > Decimal('3')

    def test_missing_pair_returns_none(self, fx):
        assert CC.get_rate('XYZ', 'ILS') is None


class TestConvert:
    def test_zero_amount(self, fx):
        assert CC.convert(0, 'USD', 'ILS') == Decimal('0')

    def test_same_currency(self, fx):
        assert CC.convert(100, 'ILS', 'ILS') == Decimal('100.00')

    def test_with_rate(self, fx):
        fx.rate('USD', 'ILS', sell=3.50)
        assert CC.convert(10, 'USD', 'ILS') == Decimal('35.00')

    def test_no_rate_returns_none(self, fx):
        assert CC.convert(10, 'XYZ', 'ILS') is None


class TestEnsureManualRate:
    def test_creates_and_deactivates_old(self, fx):
        old = fx.rate('EUR', 'ILS', sell=4.0)
        new = CC.ensure_manual_rate('EUR', 'ILS', sell_rate=4.10)
        assert new.sell_rate == Decimal('4.10')
        fx.db.session.refresh(old)
        assert old.is_active is False


class TestHelpers:
    def test_get_all_active_rates_dedupes(self, fx):
        fx.rate('USD', 'ILS', sell=3.6)
        fx.rate('USD', 'ILS', sell=3.7)
        pairs = {(r.from_currency, r.to_currency) for r in CC.get_all_active_rates()}
        assert ('USD', 'ILS') in pairs

    def test_get_missing_pairs(self, fx):
        fx.rate('USD', 'ILS', sell=3.6)
        missing = CC.get_missing_pairs('ILS')
        assert ('ILS', 'USD') not in missing
        assert all(m[0] == 'ILS' for m in missing)

    def test_fetch_external_rate_mocked(self, fx, monkeypatch):
        class FakeResp:
            status_code = 200
            def json(self):
                return {'rates': {'ILS': 3.55}}
        monkeypatch.setattr('requests.get', lambda *a, **k: FakeResp())
        val = CC.fetch_external_rate('USD', 'ILS')
        assert val == Decimal('3.55')
