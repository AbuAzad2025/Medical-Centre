"""
نماذج أسعار الصرف — Multi-Currency Exchange Rate System
"""
from datetime import datetime, timezone
from sqlalchemy import Index, CheckConstraint
from app_factory import db


class ExchangeRate(db.Model):
    """أسعار الصرف لدعم العملات المتعددة"""
    __tablename__ = 'exchange_rates'

    id = db.Column(db.Integer, primary_key=True)
    from_currency = db.Column(db.String(8), nullable=False)   # العملة المصدر (ILS, USD, EUR, JOD)
    to_currency = db.Column(db.String(8), nullable=False)     # العملة الهدف (ILS, USD, EUR, JOD)
    buy_rate = db.Column(db.Numeric(18, 6), nullable=False)   # سعر الشراء (المركز يشتري)
    sell_rate = db.Column(db.Numeric(18, 6), nullable=False)  # سعر البيع (المركز يبيع)
    effective_date = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    source = db.Column(db.String(50), nullable=False, default='MANUAL')  # MANUAL, API, EXTERNAL
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    notes = db.Column(db.Text, nullable=True)

    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        CheckConstraint("from_currency != to_currency", name='chk_diff_currencies'),
        Index('idx_exchange_currency_pair', 'from_currency', 'to_currency'),
        Index('idx_exchange_effective', 'effective_date'),
        Index('idx_exchange_active', 'is_active'),
    )

    creator = db.relationship('User', lazy='selectin')

    def __repr__(self):
        return f'<ExchangeRate {self.from_currency}->{self.to_currency} {self.buy_rate}>'

    def to_dict(self):
        return {
            'id': self.id,
            'from_currency': self.from_currency,
            'to_currency': self.to_currency,
            'buy_rate': float(self.buy_rate or 0),
            'sell_rate': float(self.sell_rate or 0),
            'effective_date': self.effective_date.isoformat() if self.effective_date else None,
            'source': self.source,
            'is_active': self.is_active,
            'notes': self.notes,
            'created_by': self.created_by,
        }


class CurrencySettings:
    """إعدادات العملات المدعومة"""
    SUPPORTED_CURRENCIES = {
        'ILS': {'name': 'شيكل إسرائيلي', 'symbol': '₪', 'flag': '🇮🇱'},
        'USD': {'name': 'دولار أمريكي', 'symbol': '$', 'flag': '🇺🇸'},
        'EUR': {'name': 'يورو', 'symbol': '€', 'flag': '🇪🇺'},
        'JOD': {'name': 'دينار أردني', 'symbol': 'د.أ', 'flag': '🇯🇴'},
        'SAR': {'name': 'ريال سعودي', 'symbol': 'ر.س', 'flag': '🇸🇦'},
        'AED': {'name': 'درهم إماراتي', 'symbol': 'د.إ', 'flag': '🇦🇪'},
        'QAR': {'name': 'ريال قطري', 'symbol': 'ر.ق', 'flag': '🇶🇦'},
        'KWD': {'name': 'دينار كويتي', 'symbol': 'د.ك', 'flag': '🇰🇼'},
        'BHD': {'name': 'دينار بحريني', 'symbol': 'د.ب', 'flag': '🇧🇭'},
        'OMR': {'name': 'ريال عماني', 'symbol': 'ر.ع', 'flag': '🇴🇲'},
    }

    DEFAULT_BASE_CURRENCY = 'ILS'

    @classmethod
    def get_all(cls):
        return cls.SUPPORTED_CURRENCIES

    @classmethod
    def get_symbol(cls, code):
        return cls.SUPPORTED_CURRENCIES.get(code, {}).get('symbol', code)

    @classmethod
    def get_name(cls, code):
        return cls.SUPPORTED_CURRENCIES.get(code, {}).get('name', code)
