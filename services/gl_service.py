"""
GLService — Chart of Accounts provisioning and double-entry journal posting.

Provides:
- ``ensure_coa`` : idempotently create the default Chart of Accounts for a tenant.
- ``seed_coa_defaults`` : returns the standard medical-center COA definitions.
- ``post_journal`` : validate and persist a balanced double-entry journal.

The posting engine enforces the fundamental accounting equation:
    total debits == total credits   (zero-sum)
and raises ``ValueError`` on an unbalanced journal so callers cannot persist
invalid accounting records.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.shared.enums import AccountNormalBalance, AccountType, JournalSourceType, JournalStatus
from app.shared.tenant_filter import _is_saas_mode
from models.gl import FinancialPeriod
from utils.db_safety import safe_commit

# Cash account codes that map a Payment.method to the receiving account.
CASH_ACCOUNT_CODE = '1000'
CARD_ACCOUNT_CODE = '1002'
WIRE_ACCOUNT_CODE = '1003'
PATIENT_RECEIVABLE_CODE = '1100'
INSURANCE_RECEIVABLE_CODE = '1105'
INVENTORY_CODE = '1300'
VENDOR_PAYABLE_CODE = '2005'
REVENUE_SERVICE_CODE = '4000'
REVENUE_PHARMACY_CODE = '4100'
COGS_CODE = '5000'
EXPENSE_OPERATING_CODE = '6000'
EXPENSE_MEDICAL_SUPPLY_CODE = '6020'
VAT_PAYABLE_CODE = '2010'
VAT_RECEIVABLE_CODE = '1200'

# Mapping of payment method -> cash/debt account code used when receiving money.
_PAYMENT_ACCOUNT_MAP = {
    'CASH': CASH_ACCOUNT_CODE,
    'FORCE': CASH_ACCOUNT_CODE,
    'CARD': CARD_ACCOUNT_CODE,
    'VISA': CARD_ACCOUNT_CODE,
    'MADA': CARD_ACCOUNT_CODE,
    'WIRE': WIRE_ACCOUNT_CODE,
    'INSURANCE': INSURANCE_RECEIVABLE_CODE,
}


class GLService:
    """Chart of Accounts + double-entry posting engine."""

    @staticmethod
    def coa_defaults() -> list[dict]:
        """Return the standard medical-center Chart of Accounts definitions.

        Each definition carries the code, name, name_ar, account_type and
        normal_balance for idempotent seeding.
        """
        return [
            # ── Assets (DR) ─────────────────────────────────────────────
            {
                'code': '1000',
                'name': 'Cash on Hand',
                'name_ar': 'النقدية بالصندوق',
                'type': AccountType.ASSET,
                'normal': AccountNormalBalance.DEBIT,
            },
            {
                'code': '1002',
                'name': 'Bank - Card Settlements',
                'name_ar': 'البنك - تسويات البطاقات',
                'type': AccountType.ASSET,
                'normal': AccountNormalBalance.DEBIT,
            },
            {
                'code': '1003',
                'name': 'Bank - Wire Transfers',
                'name_ar': 'البنك - التحويلات',
                'type': AccountType.ASSET,
                'normal': AccountNormalBalance.DEBIT,
            },
            {
                'code': '1100',
                'name': 'Patient Receivables',
                'name_ar': 'ذمم مرضى مدينة',
                'type': AccountType.ASSET,
                'normal': AccountNormalBalance.DEBIT,
            },
            {
                'code': '1105',
                'name': 'Insurance Receivables',
                'name_ar': 'ذمم تأمين مدينة',
                'type': AccountType.ASSET,
                'normal': AccountNormalBalance.DEBIT,
            },
            {
                'code': '1200',
                'name': 'VAT Receivable',
                'name_ar': 'ضريبة القيمة المضافة مدينة',
                'type': AccountType.ASSET,
                'normal': AccountNormalBalance.DEBIT,
            },
            {
                'code': '1300',
                'name': 'Inventory - Medications',
                'name_ar': 'مخزون الأدوية',
                'type': AccountType.ASSET,
                'normal': AccountNormalBalance.DEBIT,
            },
            # ── Liabilities (CR) ────────────────────────────────────────
            {
                'code': '2005',
                'name': 'Vendor Payables',
                'name_ar': 'ذمم موردين دائنة',
                'type': AccountType.LIABILITY,
                'normal': AccountNormalBalance.CREDIT,
            },
            {
                'code': '2010',
                'name': 'VAT Payable',
                'name_ar': 'ضريبة القيمة المضافة دائنة',
                'type': AccountType.LIABILITY,
                'normal': AccountNormalBalance.CREDIT,
            },
            # ── Equity (CR) ─────────────────────────────────────────────
            {
                'code': '3000',
                'name': 'Owner Equity',
                'name_ar': 'حقوق المالك',
                'type': AccountType.EQUITY,
                'normal': AccountNormalBalance.CREDIT,
            },
            # ── Revenue (CR) ────────────────────────────────────────────
            {
                'code': '4000',
                'name': 'Service Revenue',
                'name_ar': 'إيرادات الخدمات الطبية',
                'type': AccountType.REVENUE,
                'normal': AccountNormalBalance.CREDIT,
            },
            {
                'code': '4100',
                'name': 'Pharmacy Revenue',
                'name_ar': 'إيرادات الصيدلية',
                'type': AccountType.REVENUE,
                'normal': AccountNormalBalance.CREDIT,
            },
            # ── Expenses / COGS (DR) ────────────────────────────────────
            {
                'code': '5000',
                'name': 'Cost of Goods Sold',
                'name_ar': 'تكلفة البضاعة المباعة',
                'type': AccountType.EXPENSE,
                'normal': AccountNormalBalance.DEBIT,
            },
            {
                'code': '6000',
                'name': 'Operating Expenses',
                'name_ar': 'المصاريف التشغيلية',
                'type': AccountType.EXPENSE,
                'normal': AccountNormalBalance.DEBIT,
            },
            {
                'code': '6020',
                'name': 'Medical Supply Expense',
                'name_ar': 'مصاريف المستلزمات الطبية',
                'type': AccountType.EXPENSE,
                'normal': AccountNormalBalance.DEBIT,
            },
        ]

    @staticmethod
    def seed_coa(tenant_id: int | None) -> dict:
        """Idempotently create all default accounts for a tenant.

        Existing account codes are left untouched; missing ones are added.
        Caller is responsible for committing the transaction.
        """
        from models.gl import Account

        created: list[Account] = []
        for spec in GLService.coa_defaults():
            existing = (
                db.session.execute(
                    select(Account).filter_by(tenant_id=tenant_id, code=spec['code'])
                )
                .scalars()
                .first()
            )
            if existing:
                continue
            account = Account(
                tenant_id=tenant_id,
                code=spec['code'],
                name=spec['name'],
                name_ar=spec['name_ar'],
                account_type=spec['type'],
                normal_balance=spec['normal'],
                is_active=True,
            )
            db.session.add(account)
            created.append(account)
        db.session.flush()
        return {'created': len(created), 'total': len(GLService.coa_defaults())}

    @staticmethod
    def get_account(tenant_id: int | None, code: str):
        """Return an Account by code, or None."""
        from models.gl import Account

        return (
            db.session.execute(select(Account).filter_by(tenant_id=tenant_id, code=code))
            .scalars()
            .first()
        )

    @staticmethod
    def ensure_coa(tenant_id: int | None) -> None:
        """Ensure the Chart of Accounts exists for the tenant. Flushes if created."""
        from models.gl import Account

        # In SaaS/RLS mode the GUC may be lost after a savepoint commit; re-assert
        # it explicitly so the SELECT can see the tenant's existing accounts. This
        # prevents duplicate-key violations when post_* helpers run after a prior
        # commit in the same test transaction.
        if tenant_id is not None and _is_saas_mode():
            db.session.execute(
                db.text("SELECT set_config('app.tenant_id', :tid, true)"),
                {'tid': str(tenant_id)},
            )

        count = db.session.execute(select(Account).filter_by(tenant_id=tenant_id)).scalars().all()
        if not count:
            try:
                with db.session.begin_nested():
                    GLService.seed_coa(tenant_id)
            except IntegrityError:
                # Another writer already seeded the COA (e.g. a prior
                # savepoint committed). The nested rollback discards only
                # the duplicate inserts; the outer payment remains intact.
                pass

    @staticmethod
    def payment_account_for_method(method: str) -> str:
        """Map a Payment.method to the cash/receivable account code."""
        return _PAYMENT_ACCOUNT_MAP.get(str(method or '').upper(), CASH_ACCOUNT_CODE)

    @staticmethod
    def _resolve_account(tenant_id: int | None, code: str) -> Any:
        account = GLService.get_account(tenant_id, code)
        if account is None:
            raise ValueError(f'Ledger account {code!r} not found for tenant {tenant_id}')
        return account

    @staticmethod
    def ensure_financial_periods(tenant_id: int | None) -> None:
        """Create a default open period covering the current year if none exist."""

        if not tenant_id:
            return
        today = datetime.now(UTC).date()
        start = today.replace(month=1, day=1)
        end = today.replace(month=12, day=31)
        exists = (
            db.session.execute(
                select(FinancialPeriod).where(
                    FinancialPeriod.tenant_id == tenant_id,
                    FinancialPeriod.start_date == start,
                    FinancialPeriod.end_date == end,
                )
            )
            .scalars()
            .first()
        )
        if not exists:
            period = FinancialPeriod(
                tenant_id=tenant_id,
                start_date=start,
                end_date=end,
                is_closed=False,
            )
            db.session.add(period)
            db.session.flush()

    @staticmethod
    def close_period(tenant_id: int | None, period_id: int, closed_by: int | None = None) -> dict:
        """Close a financial period. Raises ValueError if already closed or not found."""

        period = db.session.get(FinancialPeriod, period_id)
        if period is None:
            raise ValueError(f'Financial period {period_id} not found')
        if period.tenant_id != tenant_id:
            raise ValueError('Period does not belong to this tenant')
        if period.is_closed:
            raise ValueError(f'Financial period {period_id} is already closed')
        period.is_closed = True
        period.closed_at = datetime.now(UTC)
        period.closed_by = closed_by
        safe_commit(db.session, error_message='Failed to close financial period', reraise=True)
        return {'period_id': period_id, 'is_closed': True, 'closed_at': period.closed_at}

    @staticmethod
    def _check_period_closed(tenant_id: int | None, transaction_date: datetime) -> None:
        """Raise ValueError if the transaction date falls inside a closed period."""

        if not tenant_id:
            return
        date = (
            transaction_date.date() if isinstance(transaction_date, datetime) else transaction_date
        )
        closed = (
            db.session.execute(
                select(FinancialPeriod).where(
                    FinancialPeriod.tenant_id == tenant_id,
                    FinancialPeriod.is_closed == True,  # noqa: E712
                    FinancialPeriod.start_date <= date,
                    FinancialPeriod.end_date >= date,
                )
            )
            .scalars()
            .first()
        )
        if closed:
            raise ValueError(
                f'Cannot post to closed financial period {closed.id} '
                f'({closed.start_date}..{closed.end_date})'
            )

    @staticmethod
    def post_payment(payment) -> dict:
        """Post a cash receipt for a confirmed payment.

        DR  Cash (or the payment method's cash/receivable account)
        CR  Service Revenue
        """
        from models.payment import Payment

        if not isinstance(payment, Payment):
            raise TypeError('payment must be a Payment instance')
        from models.gl import GLJournal

        tenant_id = getattr(payment, 'tenant_id', None)
        GLService.ensure_coa(tenant_id)
        cash_code = GLService.payment_account_for_method(payment.method)
        source_id = payment.id or 0
        # Avoid double-posting for the same payment.
        existing = (
            db.session.execute(
                select(GLJournal).filter_by(
                    tenant_id=tenant_id,
                    source_type=JournalSourceType.PAYMENT,
                    source_id=source_id,
                )
            )
            .scalars()
            .first()
        )
        if existing:
            return {'journal_id': existing.id, 'replayed': True}
        return GLService.post_journal(
            tenant_id=tenant_id,
            source_type=JournalSourceType.PAYMENT,
            source_id=source_id,
            description=f'Payment #{payment.id} via {payment.method}',
            lines=[
                {
                    'account_code': cash_code,
                    'debit': payment.amount,
                    'credit': 0,
                    'description': 'cash received',
                },
                {
                    'account_code': REVENUE_SERVICE_CODE,
                    'debit': 0,
                    'credit': payment.amount,
                    'description': 'service revenue recognized',
                },
            ],
            posted_by=getattr(payment, 'received_by', None),
        )

    @staticmethod
    def post_expense(expense) -> dict:
        """Post an operational expense.

        DR  Operating Expenses (or Medical Supply Expense)
        CR  Cash on Hand
        """
        from models.expense import Expense

        if not isinstance(expense, Expense):
            raise TypeError('expense must be an Expense instance')
        from models.gl import GLJournal

        tenant_id = getattr(expense, 'tenant_id', None)
        GLService.ensure_coa(tenant_id)
        expense_code = EXPENSE_OPERATING_CODE
        source_id = expense.id or 0
        existing = (
            db.session.execute(
                select(GLJournal).filter_by(
                    tenant_id=tenant_id,
                    source_type=JournalSourceType.EXPENSE,
                    source_id=source_id,
                )
            )
            .scalars()
            .first()
        )
        if existing:
            return {'journal_id': existing.id, 'replayed': True}
        return GLService.post_journal(
            tenant_id=tenant_id,
            source_type=JournalSourceType.EXPENSE,
            source_id=source_id,
            description=f'Expense #{expense.id} - {expense.category}',
            lines=[
                {
                    'account_code': expense_code,
                    'debit': expense.amount,
                    'credit': 0,
                    'description': expense.category,
                },
                {
                    'account_code': CASH_ACCOUNT_CODE,
                    'debit': 0,
                    'credit': expense.amount,
                    'description': 'cash paid out',
                },
            ],
            posted_by=getattr(expense, 'recorded_by_id', None),
        )

    @staticmethod
    def post_refund(payment, refund) -> dict:
        """Post a reversing entry for an executed refund.

        DR  Service Revenue
        CR  Cash (or the original payment method's account)
        """
        from models.gl import GLJournal

        tenant_id = getattr(payment, 'tenant_id', None)
        GLService.ensure_coa(tenant_id)
        cash_code = GLService.payment_account_for_method(payment.method)
        source_id = refund.id or 0
        existing = (
            db.session.execute(
                select(GLJournal).filter_by(
                    tenant_id=tenant_id,
                    source_type=JournalSourceType.REFUND,
                    source_id=source_id,
                )
            )
            .scalars()
            .first()
        )
        if existing:
            return {'journal_id': existing.id, 'replayed': True}
        return GLService.post_journal(
            tenant_id=tenant_id,
            source_type=JournalSourceType.REFUND,
            source_id=source_id,
            description=f'Refund #{refund.id} for payment #{payment.id}',
            lines=[
                {
                    'account_code': REVENUE_SERVICE_CODE,
                    'debit': refund.amount,
                    'credit': 0,
                    'description': 'revenue reversed',
                },
                {
                    'account_code': cash_code,
                    'debit': 0,
                    'credit': refund.amount,
                    'description': 'cash refunded',
                },
            ],
            posted_by=getattr(refund, 'executed_by', None),
        )

    @staticmethod
    def post_procurement(medication_purchase) -> dict:
        """Post a medication purchase.

        DR  Inventory - Medications
        CR  Vendor Payables
        """
        from models.gl import GLJournal

        tenant_id = getattr(medication_purchase, 'tenant_id', None)
        GLService.ensure_coa(tenant_id)
        amount = Decimal(str(medication_purchase.purchase_price or 0)) * Decimal(
            int(medication_purchase.quantity or 0)
        )
        source_id = medication_purchase.id or 0
        existing = (
            db.session.execute(
                select(GLJournal).filter_by(
                    tenant_id=tenant_id,
                    source_type=JournalSourceType.PROCUREMENT,
                    source_id=source_id,
                )
            )
            .scalars()
            .first()
        )
        if existing:
            return {'journal_id': existing.id, 'replayed': True}
        return GLService.post_journal(
            tenant_id=tenant_id,
            source_type=JournalSourceType.PROCUREMENT,
            source_id=source_id,
            description=f'Purchase #{medication_purchase.id} received',
            lines=[
                {
                    'account_code': INVENTORY_CODE,
                    'debit': amount,
                    'credit': 0,
                    'description': 'inventory received',
                },
                {
                    'account_code': VENDOR_PAYABLE_CODE,
                    'debit': 0,
                    'credit': amount,
                    'description': 'vendor payable',
                },
            ],
            posted_by=getattr(medication_purchase, 'created_by', None),
        )

    @staticmethod
    def post_pharmacy_sale(sale, cost_amount) -> dict:
        """Post a pharmacy sale with revenue and COGS.

        DR  Cash / Bank
        CR  Pharmacy Revenue
        DR  Cost of Goods Sold
        CR  Inventory - Medications
        """
        from models.gl import GLJournal

        tenant_id = getattr(sale, 'tenant_id', None)
        GLService.ensure_coa(tenant_id)
        source_id = sale.id or 0
        existing = (
            db.session.execute(
                select(GLJournal).filter_by(
                    tenant_id=tenant_id,
                    source_type=JournalSourceType.PHARMACY_SALE,
                    source_id=source_id,
                )
            )
            .scalars()
            .first()
        )
        if existing:
            return {'journal_id': existing.id, 'replayed': True}
        revenue = Decimal(str(sale.total_amount or 0)).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        cost = Decimal(str(cost_amount or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        lines = [
            {
                'account_code': CASH_ACCOUNT_CODE,
                'debit': revenue,
                'credit': 0,
                'description': 'pharmacy sale cash',
            },
            {
                'account_code': REVENUE_PHARMACY_CODE,
                'debit': 0,
                'credit': revenue,
                'description': 'pharmacy revenue',
            },
        ]
        if cost > 0:
            lines.append(
                {
                    'account_code': COGS_CODE,
                    'debit': cost,
                    'credit': 0,
                    'description': 'cost of goods sold',
                }
            )
            lines.append(
                {
                    'account_code': INVENTORY_CODE,
                    'debit': 0,
                    'credit': cost,
                    'description': 'inventory reduction',
                }
            )
        return GLService.post_journal(
            tenant_id=tenant_id,
            source_type=JournalSourceType.PHARMACY_SALE,
            source_id=source_id,
            description=f'Pharmacy sale #{sale.id}',
            lines=lines,
            posted_by=getattr(sale, 'created_by', None),
        )

    @staticmethod
    def post_journal(
        *,
        tenant_id: int | None,
        source_type: str,
        source_id: int,
        description: str | None,
        lines: list[dict],
        posted_by: int | None = None,
    ) -> dict:
        """Post a double-entry journal.

        ``lines`` is a list of dicts::
            {'account_code': str, 'debit': Decimal, 'credit': Decimal,
             'description': str|None}

        Validates that the journal is balanced (sum(debits) == sum(credits))
        and that each line references a real account. Returns a summary dict.
        """
        from models.gl import GLJournal, GLJournalLine

        if not lines:
            raise ValueError('Journal must contain at least one line')

        GLService._check_period_closed(tenant_id, datetime.now(UTC))

        debit_total = Decimal(0)
        credit_total = Decimal(0)
        normalized: list[dict] = []
        for line in lines:
            code = line.get('account_code')
            account = GLService._resolve_account(tenant_id, code)
            debit = Decimal(str(line.get('debit') or 0)).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            credit = Decimal(str(line.get('credit') or 0)).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )
            if debit < 0 or credit < 0:
                raise ValueError('Debit and credit amounts must be non-negative')
            if debit > 0 and credit > 0:
                raise ValueError(f'Line for account {code} has both debit and credit set')
            deferred_description = line.get('description')
            if debit == 0 and credit == 0:
                continue
            debit_total += debit
            credit_total += credit
            normalized.append(
                {
                    'account_id': account.id,
                    'debit': debit,
                    'credit': credit,
                    'description': deferred_description,
                }
            )

        if not normalized:
            raise ValueError('Journal contains no non-zero lines')

        if debit_total != credit_total:
            raise ValueError(f'Unbalanced journal: debits={debit_total} credits={credit_total}')

        journal = GLJournal(
            tenant_id=tenant_id,
            journal_number=f'JRN-{uuid.uuid4().hex[:8].upper()}',
            journal_date=datetime.now(UTC),
            description=description,
            status=JournalStatus.POSTED,
            source_type=source_type,
            source_id=source_id,
            posted_by=posted_by,
        )
        db.session.add(journal)
        db.session.flush()

        for norm in normalized:
            line = GLJournalLine(
                tenant_id=tenant_id,
                journal_id=journal.id,
                account_id=norm['account_id'],
                debit_amount=norm['debit'],
                credit_amount=norm['credit'],
                line_description=norm['description'],
            )
            db.session.add(line)
        db.session.flush()

        return {
            'journal_id': journal.id,
            'debit_total': float(debit_total),
            'credit_total': float(credit_total),
        }


# Singleton
gl_service = GLService()
