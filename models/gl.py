"""
General Ledger & Chart of Accounts models.

Provides:
- Account  : the Chart of Accounts hierarchy with normal balances.
- GLJournal   : a posted journal entry (balanced, double-entry).
- GLJournalLine : the individual debit/credit lines of a journal entry.

All financial transaction services post against these tables via
``services.gl_service.GLService``, which validates that each journal is
balanced (sum of debits == sum of credits) before committing.
"""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Index, UniqueConstraint

from app.shared.enums import AccountNormalBalance, AccountType, JournalStatus
from app.shared.mixins import TenantMixin
from app_factory import db


class Account(TenantMixin, db.Model):
    """Chart of Accounts account definition with a normal balance."""

    __tablename__ = 'accounts'
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    name_ar = db.Column(db.String(120), nullable=True)
    account_type = db.Column(db.String(20), nullable=False, default=AccountType.ASSET, index=True)
    normal_balance = db.Column(
        db.String(20), nullable=False, default=AccountNormalBalance.DEBIT, index=True
    )
    parent_id = db.Column(
        db.Integer, db.ForeignKey('accounts.id', ondelete='SET NULL'), nullable=True, index=True
    )
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    parent = db.relationship('Account', remote_side=[id], lazy='selectin')

    __table_args__ = (
        UniqueConstraint('tenant_id', 'code', name='uq_accounts_tenant_code'),
        CheckConstraint(
            "account_type IN ('ASSET', 'LIABILITY', 'EQUITY', 'REVENUE', 'EXPENSE')",
            name='chk_account_type',
        ),
        CheckConstraint("normal_balance IN ('DEBIT', 'CREDIT')", name='chk_account_normal_balance'),
        Index('idx_accounts_tenant_type', 'tenant_id', 'account_type'),
        Index('idx_accounts_tenant_normal', 'tenant_id', 'normal_balance'),
    )

    def __repr__(self) -> str:
        return f'<Account {self.code} {self.name}>'

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'code': self.code,
            'name': self.name,
            'name_ar': self.name_ar,
            'account_type': self.account_type,
            'normal_balance': self.normal_balance,
            'parent_id': self.parent_id,
            'is_active': self.is_active,
            'description': self.description,
        }


class FinancialPeriod(TenantMixin, db.Model):
    """A closed or open financial accounting period."""

    __tablename__ = 'financial_periods'
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)
    start_date = db.Column(db.Date, nullable=False, index=True)
    end_date = db.Column(db.Date, nullable=False, index=True)
    is_closed = db.Column(db.Boolean, default=False, nullable=False, index=True)
    closed_at = db.Column(db.DateTime, nullable=True)
    closed_by = db.Column(
        db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True
    )

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    closed_by_user = db.relationship('User', foreign_keys=[closed_by], lazy='selectin')

    __table_args__ = (
        CheckConstraint('end_date >= start_date', name='chk_period_end_ge_start'),
        UniqueConstraint('tenant_id', 'start_date', 'end_date', name='uq_periods_tenant_dates'),
        Index('idx_periods_tenant_closed', 'tenant_id', 'is_closed'),
    )

    def __repr__(self) -> str:
        return f'<FinancialPeriod {self.id} {self.start_date}..{self.end_date} closed={self.is_closed}>'

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'is_closed': self.is_closed,
            'closed_at': self.closed_at.isoformat() if self.closed_at else None,
            'closed_by': self.closed_by,
        }


class GLJournal(TenantMixin, db.Model):
    """A posted double-entry journal entry (aggregate of lines)."""

    __tablename__ = 'gl_journals'
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)
    journal_number = db.Column(db.String(40), nullable=True, index=True)
    journal_date = db.Column(
        db.DateTime, nullable=False, index=True, default=lambda: datetime.now(UTC)
    )
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default=JournalStatus.POSTED, index=True)

    source_type = db.Column(db.String(32), nullable=False, index=True)
    source_id = db.Column(db.Integer, nullable=False, index=True)

    posted_by = db.Column(
        db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True
    )
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(UTC), nullable=False, index=True
    )

    lines = db.relationship(
        'GLJournalLine',
        back_populates='journal',
        lazy='selectin',
        cascade='all, delete-orphan',
        passive_deletes=True,
    )

    __table_args__ = (
        Index('idx_gl_journals_tenant_source', 'tenant_id', 'source_type', 'source_id'),
        CheckConstraint("status IN ('POSTED', 'VOID')", name='chk_gl_journal_status'),
    )

    def __repr__(self) -> str:
        return f'<GLJournal #{self.id} {self.source_type}:{self.source_id}>'

    def total_debit(self) -> Decimal:
        return sum((Decimal(str(line.debit_amount or 0)) for line in self.lines), Decimal(0))

    def total_credit(self) -> Decimal:
        return sum((Decimal(str(line.credit_amount or 0)) for line in self.lines), Decimal(0))

    def is_balanced(self) -> bool:
        return self.total_debit() == self.total_credit()

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'journal_number': self.journal_number,
            'journal_date': self.journal_date.isoformat() if self.journal_date else None,
            'description': self.description,
            'status': self.status,
            'source_type': self.source_type,
            'source_id': self.source_id,
            'posted_by': self.posted_by,
            'total_debit': float(self.total_debit()),
            'total_credit': float(self.total_credit()),
            'lines': [line.to_dict() for line in self.lines],
        }


class GLJournalLine(TenantMixin, db.Model):
    """A single debit/credit line within a GL journal entry."""

    __tablename__ = 'gl_journal_lines'
    __tenant_migration__ = True

    id = db.Column(db.Integer, primary_key=True)
    journal_id = db.Column(
        db.Integer, db.ForeignKey('gl_journals.id', ondelete='CASCADE'), nullable=False, index=True
    )
    account_id = db.Column(
        db.Integer, db.ForeignKey('accounts.id', ondelete='RESTRICT'), nullable=False, index=True
    )
    debit_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    credit_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    line_description = db.Column(db.Text, nullable=True)

    journal = db.relationship('GLJournal', back_populates='lines', lazy='selectin')
    account = db.relationship('Account', lazy='selectin')

    __table_args__ = (
        CheckConstraint('debit_amount >= 0', name='chk_gl_line_debit_non_negative'),
        CheckConstraint('credit_amount >= 0', name='chk_gl_line_credit_non_negative'),
        Index('idx_gl_lines_journal', 'journal_id'),
        Index('idx_gl_lines_account', 'account_id'),
    )

    def __repr__(self) -> str:
        return (
            f'<GLJournalLine acct {self.account_id} dr {self.debit_amount} cr {self.credit_amount}>'
        )

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'journal_id': self.journal_id,
            'account_id': self.account_id,
            'account_code': self.account.code if self.account else None,
            'debit_amount': float(self.debit_amount or 0),
            'credit_amount': float(self.credit_amount or 0),
            'line_description': self.line_description,
        }
