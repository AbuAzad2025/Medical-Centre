"""Operational expense tracking for finance and manager dashboards."""
from datetime import date, datetime, timezone

from sqlalchemy import Index

from app_factory import db
from app.shared.mixins import TenantMixin


class Expense(TenantMixin, db.Model):
    __tablename__ = 'expenses'
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False, index=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    description = db.Column(db.Text, nullable=True)
    recorded_by_id = db.Column(
        db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True,
    )
    expense_date = db.Column(db.Date, nullable=False, index=True, default=date.today)
    status = db.Column(db.String(20), default='RECORDED', nullable=False, index=True)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True,
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    recorded_by = db.relationship('User', foreign_keys=[recorded_by_id], lazy='selectin')
    approver = db.relationship('User', foreign_keys=[approved_by], lazy='selectin')

    __table_args__ = (
        Index('idx_expense_tenant_date', 'tenant_id', 'expense_date'),
        Index('idx_expense_tenant_category', 'tenant_id', 'category'),
    )

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'category': self.category,
            'amount': float(self.amount or 0),
            'description': self.description,
            'recorded_by_id': self.recorded_by_id,
            'expense_date': self.expense_date.isoformat() if self.expense_date else None,
            'status': self.status,
            'approved_by': self.approved_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return f'<Expense {self.category} {self.amount}>'
