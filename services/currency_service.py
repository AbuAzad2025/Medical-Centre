"""
خدمة تحويل العملات — Currency Conversion Service
Priority: Manual Rate → External API → Modal Prompt (fallback)
"""
import logging
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone, timedelta
from app_factory import db

logger = logging.getLogger(__name__)


class CurrencyConverter:
    """محول العملات الرئيسي"""

    @classmethod
    def get_rate(cls, from_currency, to_currency):
        """
        الحصول على سعر الصرف:
        1. ابحث عن سعر يدوي نشط (MANUAL)
        2. ابحث عن سعر API نشط
        3. ارجع None ليطلب المستخدم إدخال سعر يدوياً
        """
        if from_currency == to_currency:
            return Decimal('1.0')

        from models.exchange_rate import ExchangeRate

        # 1. السعر اليدوي الأحدث النشط
        rate = ExchangeRate.query.filter(
            ExchangeRate.from_currency == from_currency,
            ExchangeRate.to_currency == to_currency,
            ExchangeRate.is_active == True,
            ExchangeRate.source == 'MANUAL'
        ).order_by(ExchangeRate.effective_date.desc()).first()

        if rate:
            logger.info(f"Using MANUAL rate {from_currency}->{to_currency}: {rate.sell_rate}")
            return Decimal(str(rate.sell_rate))

        # 2. سعر API الأحدث (أقل من 24 ساعة)
        api_rate = ExchangeRate.query.filter(
            ExchangeRate.from_currency == from_currency,
            ExchangeRate.to_currency == to_currency,
            ExchangeRate.is_active == True,
            ExchangeRate.source == 'API',
            ExchangeRate.effective_date >= (datetime.now(timezone.utc) - timedelta(hours=24))
        ).order_by(ExchangeRate.effective_date.desc()).first()

        if api_rate:
            logger.info(f"Using API rate {from_currency}->{to_currency}: {api_rate.sell_rate}")
            return Decimal(str(api_rate.sell_rate))

        # 3. السعر العكسي (inverse) إن وجد
        inverse = ExchangeRate.query.filter(
            ExchangeRate.from_currency == to_currency,
            ExchangeRate.to_currency == from_currency,
            ExchangeRate.is_active == True
        ).order_by(ExchangeRate.effective_date.desc()).first()

        if inverse:
            inv = Decimal('1.0') / Decimal(str(inverse.buy_rate))
            logger.info(f"Using INVERSE rate {from_currency}->{to_currency}: {inv}")
            return inv.quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP)

        logger.warning(f"No rate found for {from_currency}->{to_currency}")
        return None

    @classmethod
    def convert(cls, amount, from_currency, to_currency, use_sell=True):
        """تحويل مبلغ من عملة إلى أخرى"""
        if not amount:
            return Decimal('0')
        if from_currency == to_currency:
            return Decimal(str(amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        rate = cls.get_rate(from_currency, to_currency)
        if rate is None:
            return None  # يجب طلب سعر يدوي

        result = Decimal(str(amount)) * rate
        return result.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @classmethod
    def ensure_manual_rate(cls, from_currency, to_currency, sell_rate, buy_rate=None, user_id=None):
        """إنشاء/تحديث سعر يدوي"""
        from models.exchange_rate import ExchangeRate
        buy = buy_rate or sell_rate
        rate = ExchangeRate(
            from_currency=from_currency,
            to_currency=to_currency,
            buy_rate=Decimal(str(buy)),
            sell_rate=Decimal(str(sell_rate)),
            source='MANUAL',
            is_active=True,
            created_by=user_id,
            effective_date=datetime.now(timezone.utc),
        )
        # ألغِ السعر اليدوي القديم
        ExchangeRate.query.filter(
            ExchangeRate.from_currency == from_currency,
            ExchangeRate.to_currency == to_currency,
            ExchangeRate.source == 'MANUAL'
        ).update({'is_active': False}, synchronize_session=False)
        db.session.add(rate)
        db.session.commit()
        return rate

    @classmethod
    def fetch_external_rate(cls, from_currency, to_currency):
        """جلب سعر خارجي من API مجاني ( exchangerate-api.com أو Frankfurter )"""
        try:
            import requests
            # استخدم Frankfurter API (مجاني، لا يحتاج مفتاح)
            url = f"https://api.frankfurter.app/latest?from={from_currency}&to={to_currency}"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                rate_val = data.get('rates', {}).get(to_currency)
                if rate_val:
                    from models.exchange_rate import ExchangeRate
                    rate = ExchangeRate(
                        from_currency=from_currency,
                        to_currency=to_currency,
                        buy_rate=Decimal(str(rate_val)),
                        sell_rate=Decimal(str(rate_val)),
                        source='API',
                        is_active=True,
                        effective_date=datetime.now(timezone.utc),
                    )
                    db.session.add(rate)
                    db.session.commit()
                    logger.info(f"Fetched external rate {from_currency}->{to_currency}: {rate_val}")
                    return Decimal(str(rate_val))
        except Exception as e:
            logger.warning(f"External API failed: {e}")
        return None

    @classmethod
    def get_all_active_rates(cls):
        """جلب كل الأسعار النشطة"""
        from models.exchange_rate import ExchangeRate
        rates = ExchangeRate.query.filter(
            ExchangeRate.is_active == True
        ).order_by(ExchangeRate.from_currency, ExchangeRate.to_currency, ExchangeRate.effective_date.desc()).all()
        # أزل التكرارات (احتفظ بالأحدث لكل pair)
        seen = set()
        unique = []
        for r in rates:
            key = (r.from_currency, r.to_currency)
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique

    @classmethod
    def get_missing_pairs(cls, base_currency='ILS'):
        """الأزواج التي لا يوجد لها سعر"""
        from models.exchange_rate import CurrencySettings
        codes = list(CurrencySettings.SUPPORTED_CURRENCIES.keys())
        missing = []
        for c in codes:
            if c == base_currency:
                continue
            rate = cls.get_rate(base_currency, c)
            if rate is None:
                missing.append((base_currency, c))
        return missing
