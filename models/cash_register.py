from datetime import datetime, timezone, date, time
from app.extensions import db
from utils.db_safety import safe_commit, safe_rollback
from app.shared.mixins import TenantMixin
import logging
from sqlalchemy import select


class CashRegister(TenantMixin, db.Model):
    """نموذج سجل الصندوق اليومي - Cash Register / Till"""
    __tablename__ = 'cash_registers'

    id = db.Column(db.Integer, primary_key=True)
    register_date = db.Column(db.Date, nullable=False, default=date.today, index=True)
    opened_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    closed_at = db.Column(db.DateTime, nullable=True)

    # Opening float (رصيد الافتتاح)
    opening_cash = db.Column(db.Numeric(12, 2), default=0)
    opening_card = db.Column(db.Numeric(12, 2), default=0)
    opening_insurance = db.Column(db.Numeric(12, 2), default=0)

    # Expected totals (المتوقع من الزيارات)
    expected_cash = db.Column(db.Numeric(12, 2), default=0)
    expected_card = db.Column(db.Numeric(12, 2), default=0)
    expected_insurance = db.Column(db.Numeric(12, 2), default=0)
    expected_total = db.Column(db.Numeric(12, 2), default=0)

    # Actual counted (الفعلي)
    actual_cash = db.Column(db.Numeric(12, 2), nullable=True)
    actual_card = db.Column(db.Numeric(12, 2), nullable=True)
    actual_insurance = db.Column(db.Numeric(12, 2), nullable=True)
    actual_total = db.Column(db.Numeric(12, 2), nullable=True)

    # Variance (الفرق)
    variance = db.Column(db.Numeric(12, 2), nullable=True)

    # Status
    is_open = db.Column(db.Boolean, default=True)
    is_closed = db.Column(db.Boolean, default=False)

    # Shift info
    shift_name = db.Column(db.String(50), nullable=True)  # morning, evening, night
    receptionist_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)

    # Audit
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    receptionist = db.relationship('User', foreign_keys=[receptionist_id])

    @classmethod
    def get_or_create_today(cls, user_id=None):
        try:
            today = date.today()
            reg = db.session.execute(select(cls).filter_by(register_date=today, is_closed=False)).scalars().first()
            if not reg:
                reg = cls(
                    register_date=today,
                    receptionist_id=user_id,
                    shift_name='morning',
                    is_open=True
                )
                db.session.add(reg)
                safe_commit(db.session, error_message="database commit failed", reraise=True)
            return reg
        except Exception as e:
            safe_rollback(db.session, error_message="database rollback")
            logging.error("CashRegister.get_or_create_today failed")
            raise

    def to_dict(self):
        return {
            'id': self.id,
            'register_date': self.register_date.isoformat(),
            'is_open': self.is_open,
            'is_closed': self.is_closed,
            'opening_cash': float(self.opening_cash or 0),
            'expected_total': float(self.expected_total or 0),
            'actual_total': float(self.actual_total or 0) if self.actual_total else None,
            'variance': float(self.variance or 0) if self.variance else None,
        }
