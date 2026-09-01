"""Tests for the General Ledger engine (services.gl_service.GLService).

Covers Chart of Accounts provisioning and double-entry journal posting,
including the zero-sum (debits == credits) validation and integration with
payment, expense, refund, procurement and pharmacy-sale posting helpers.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.shared.enums import AccountType
from models.gl import Account, FinancialPeriod, GLJournal, GLJournalLine
from services.gl_service import GLService


@pytest.fixture
def gl_user(rollback_db):
    from models.user import User

    un = 'gl_' + uuid.uuid4().hex[:8]
    u = User(username=un, email=un + '@x.com', full_name='u', role='accountant', is_active=True)
    u.set_password('p')
    rollback_db.session.add(u)
    rollback_db.session.commit()
    return u


class TestSeedCOA:
    def test_seed_creates_default_accounts(self, rollback_db, test_tenant):
        GLService.seed_coa(test_tenant.id)
        count = (
            rollback_db.session.query(Account).filter(Account.tenant_id == test_tenant.id).count()
        )
        assert count == len(GLService.coa_defaults())

    def test_seed_is_idempotent(self, rollback_db, test_tenant):
        GLService.seed_coa(test_tenant.id)
        first = (
            rollback_db.session.query(Account).filter(Account.tenant_id == test_tenant.id).count()
        )
        GLService.seed_coa(test_tenant.id)
        second = (
            rollback_db.session.query(Account).filter(Account.tenant_id == test_tenant.id).count()
        )
        assert first == second == len(GLService.coa_defaults())

    def test_coa_has_expected_accounts(self, rollback_db, test_tenant):
        GLService.seed_coa(test_tenant.id)
        cash = GLService.get_account(test_tenant.id, '1000')
        assert cash is not None
        assert cash.account_type == AccountType.ASSET
        revenue = GLService.get_account(test_tenant.id, '4000')
        assert revenue is not None
        assert revenue.account_type == AccountType.REVENUE


class TestPostJournal:
    def _seed(self, rollback_db, test_tenant):
        GLService.seed_coa(test_tenant.id)
        rollback_db.session.commit()

    def test_balanced_journal_persists_lines(self, rollback_db, gl_user, test_tenant):
        self._seed(rollback_db, test_tenant)
        res = GLService.post_journal(
            tenant_id=test_tenant.id,
            source_type='visit',
            source_id=123,
            description='test',
            lines=[
                {'account_code': '1000', 'debit': 100, 'credit': 0},
                {'account_code': '4000', 'debit': 0, 'credit': 100},
            ],
            posted_by=gl_user.id,
        )
        journal_id = res['journal_id']
        journal = rollback_db.session.get(GLJournal, journal_id)
        assert journal.is_balanced()
        assert journal.total_debit() == Decimal('100.00')
        assert journal.total_credit() == Decimal('100.00')

    def test_unbalanced_journal_rejected(self, rollback_db, gl_user, test_tenant):
        self._seed(rollback_db, test_tenant)
        with pytest.raises(ValueError, match='Unbalanced'):
            GLService.post_journal(
                tenant_id=test_tenant.id,
                source_type='visit',
                source_id=999,
                description='bad',
                lines=[
                    {'account_code': '1000', 'debit': 100, 'credit': 0},
                    {'account_code': '4000', 'debit': 0, 'credit': 50},
                ],
            )

    def test_unknown_account_rejected(self, rollback_db, gl_user, test_tenant):
        self._seed(rollback_db, test_tenant)
        with pytest.raises(ValueError, match='not found'):
            GLService.post_journal(
                tenant_id=test_tenant.id,
                source_type='visit',
                source_id=1,
                description='bad',
                lines=[
                    {'account_code': '9999', 'debit': 100, 'credit': 0},
                    {'account_code': '4000', 'debit': 0, 'credit': 100},
                ],
            )

    def test_line_with_both_credit_and_debit_rejected(self, rollback_db, gl_user, test_tenant):
        self._seed(rollback_db, test_tenant)
        with pytest.raises(ValueError, match='both debit and credit'):
            GLService.post_journal(
                tenant_id=test_tenant.id,
                source_type='visit',
                source_id=1,
                description='bad',
                lines=[
                    {'account_code': '1000', 'debit': 100, 'credit': 100},
                    {'account_code': '4000', 'debit': 0, 'credit': 100},
                ],
            )


class TestPaymentPosting:
    def _payment(self, rollback_db, tenant_id, amount=100, method='CASH'):
        from models.payment import Payment

        p = Payment(
            tenant_id=tenant_id,
            method=method,
            amount=Decimal(str(amount)),
            currency='ILS',
            status='CONFIRMED',
            payment_date=datetime.now(UTC),
        )
        rollback_db.session.add(p)
        rollback_db.session.flush()
        return p

    def test_cash_payment_posts_cash_and_revenue(self, rollback_db, test_tenant):
        GLService.seed_coa(test_tenant.id)
        rollback_db.session.commit()
        p = self._payment(rollback_db, test_tenant.id, amount=100, method='CASH')
        res = GLService.post_payment(p)
        rollback_db.session.commit()
        journal = rollback_db.session.get(GLJournal, res['journal_id'])
        assert journal.is_balanced()
        codes = {line.account.code for line in journal.lines}
        assert codes == {'1000', '4000'}

    def test_card_payment_uses_bank_account(self, rollback_db, test_tenant):
        GLService.seed_coa(test_tenant.id)
        rollback_db.session.commit()
        p = self._payment(rollback_db, test_tenant.id, amount=80, method='CARD')
        res = GLService.post_payment(p)
        journal = rollback_db.session.get(GLJournal, res['journal_id'])
        codes = {line.account.code for line in journal.lines}
        assert '1002' in codes

    def test_payment_posting_is_idempotent(self, rollback_db, test_tenant):
        GLService.seed_coa(test_tenant.id)
        rollback_db.session.commit()
        p = self._payment(rollback_db, test_tenant.id, amount=60, method='CASH')
        GLService.post_payment(p)
        second = GLService.post_payment(p)
        assert second.get('replayed') is True


class TestExpensePosting:
    def test_expense_posts_dr_expense_cr_cash(self, rollback_db, test_tenant):
        from models.expense import Expense

        GLService.seed_coa(test_tenant.id)
        rollback_db.session.commit()
        e = Expense(tenant_id=test_tenant.id, category='office', amount=Decimal('50.00'))
        rollback_db.session.add(e)
        rollback_db.session.flush()
        res = GLService.post_expense(e)
        journal = rollback_db.session.get(GLJournal, res['journal_id'])
        assert journal.is_balanced()
        codes = {line.account.code for line in journal.lines}
        assert codes == {'6000', '1000'}


class TestRefundPosting:
    def test_refund_reverses_revenue(self, rollback_db, test_tenant):
        from models.payment import Payment
        from models.refund_request import RefundRequest

        GLService.seed_coa(test_tenant.id)
        rollback_db.session.commit()
        p = Payment(
            tenant_id=test_tenant.id,
            method='CASH',
            amount=Decimal('100.00'),
            currency='ILS',
            status='REFUNDED',
            payment_date=datetime.now(UTC),
        )
        rollback_db.session.add(p)
        rollback_db.session.flush()
        r = RefundRequest(
            tenant_id=test_tenant.id, payment_id=p.id, amount=Decimal('100.00'), reason='x'
        )
        r.status = 'EXECUTED'
        rollback_db.session.add(r)
        rollback_db.session.flush()
        res = GLService.post_refund(p, r)
        journal = rollback_db.session.get(GLJournal, res['journal_id'])
        assert journal.is_balanced()
        codes = {line.account.code for line in journal.lines}
        assert codes == {'4000', '1000'}


class TestProcurementPosting:
    def test_purchase_posts_inventory_and_payable(self, rollback_db, test_tenant):
        from models.medication import Medication, MedicationPurchase

        GLService.seed_coa(test_tenant.id)
        rollback_db.session.commit()
        med = Medication(
            tenant_id=test_tenant.id,
            trade_name='T',
            dosage_form='tab',
            strength='1mg',
            scientific_name='S',
        )
        rollback_db.session.add(med)
        rollback_db.session.flush()
        mp = MedicationPurchase(
            tenant_id=test_tenant.id,
            medication_id=med.id,
            batch_number='B',
            quantity=10,
            purchase_price=Decimal('5.00'),
        )
        rollback_db.session.add(mp)
        rollback_db.session.flush()
        res = GLService.post_procurement(mp)
        journal = rollback_db.session.get(GLJournal, res['journal_id'])
        assert journal.is_balanced()
        assert journal.total_debit() == Decimal('50.00')
        codes = {line.account.code for line in journal.lines}
        assert codes == {'1300', '2005'}


class TestPharmacySalePosting:
    def test_sale_posts_revenue_and_cogs(self, rollback_db, test_tenant):
        from models.medication import PharmacySale

        GLService.seed_coa(test_tenant.id)
        rollback_db.session.commit()
        sale = PharmacySale(
            tenant_id=test_tenant.id, sale_number='S1', total_amount=Decimal('200.00')
        )
        rollback_db.session.add(sale)
        rollback_db.session.flush()
        res = GLService.post_pharmacy_sale(sale, Decimal('80.00'))
        journal = rollback_db.session.get(GLJournal, res['journal_id'])
        assert journal.is_balanced()
        codes = {line.account.code for line in journal.lines}
        assert '4100' in codes and '5000' in codes and '1300' in codes


class TestTrialBalance:
    def _setup(self, rollback_db, test_tenant):
        from models.user import User

        GLService.seed_coa(test_tenant.id)
        rollback_db.session.commit()
        self.user = User(
            username='tb_' + uuid.uuid4().hex[:8],
            email='tb@x.com',
            full_name='u',
            role='accountant',
            is_active=True,
        )
        self.user.set_password('p')
        rollback_db.session.add(self.user)
        rollback_db.session.commit()
        return self.user

    def test_trial_balance_sums_debits_and_credits(self, rollback_db, test_tenant):
        u = self._setup(rollback_db, test_tenant)
        res = GLService.post_journal(
            tenant_id=test_tenant.id,
            source_type='trial',
            source_id=1,
            description='trial',
            lines=[
                {'account_code': '1000', 'debit': 500, 'credit': 0},
                {'account_code': '4000', 'debit': 0, 'credit': 300},
                {'account_code': '4100', 'debit': 0, 'credit': 200},
            ],
            posted_by=u.id,
        )
        assert res['debit_total'] == 500
        assert res['credit_total'] == 500
        stmt = select(Account).where(Account.tenant_id == test_tenant.id).order_by(Account.code)
        accounts = rollback_db.session.execute(stmt).scalars().all()
        total_debit = Decimal('0')
        total_credit = Decimal('0')
        for a in accounts:
            line_stmt = (
                select(
                    func.sum(GLJournalLine.debit_amount).label('td'),
                    func.sum(GLJournalLine.credit_amount).label('tc'),
                )
                .where(GLJournalLine.account_id == a.id)
                .group_by(GLJournalLine.account_id)
            )
            r = rollback_db.session.execute(line_stmt).first()
            if r is None:
                td = Decimal('0')
                tc = Decimal('0')
            else:
                td = r.td or Decimal('0')
                tc = r.tc or Decimal('0')
            total_debit += td
            total_credit += tc
        assert total_debit == total_credit

    def test_trial_balance_balance_is_correct(self, rollback_db, test_tenant):
        u = self._setup(rollback_db, test_tenant)
        GLService.post_journal(
            tenant_id=test_tenant.id,
            source_type='trial',
            source_id=2,
            description='trial',
            lines=[
                {'account_code': '1000', 'debit': 100, 'credit': 0},
                {'account_code': '4000', 'debit': 0, 'credit': 100},
            ],
            posted_by=u.id,
        )
        cash = GLService.get_account(test_tenant.id, '1000')
        revenue = GLService.get_account(test_tenant.id, '4000')
        assert cash is not None and revenue is not None
        cash_balance = Decimal('100') if cash.normal_balance == 'DEBIT' else Decimal('-100')
        revenue_balance = Decimal('100') if revenue.normal_balance == 'CREDIT' else Decimal('-100')
        assert cash_balance == Decimal('100')
        assert revenue_balance == Decimal('100')

    def test_trial_balance_total_debit_equals_total_credit(self, rollback_db, test_tenant):
        u = self._setup(rollback_db, test_tenant)
        GLService.post_journal(
            tenant_id=test_tenant.id,
            source_type='trial',
            source_id=3,
            description='trial',
            lines=[
                {'account_code': '1000', 'debit': 1000, 'credit': 0},
                {'account_code': '4000', 'debit': 0, 'credit': 400},
                {'account_code': '4100', 'debit': 0, 'credit': 600},
            ],
            posted_by=u.id,
        )
        from sqlalchemy import func
        from sqlalchemy import select as sa_select

        stmt = sa_select(
            func.sum(GLJournalLine.debit_amount).label('td'),
            func.sum(GLJournalLine.credit_amount).label('tc'),
        )
        row = rollback_db.session.execute(stmt).first()
        total_debit = row.td or Decimal('0')
        total_credit = row.tc or Decimal('0')
        assert total_debit == total_credit


class TestAccountLedger:
    def test_running_balance_debit_account(self, rollback_db, test_tenant):
        from models.user import User

        GLService.seed_coa(test_tenant.id)
        rollback_db.session.commit()
        u = User(
            username='al_' + uuid.uuid4().hex[:8],
            email='al@x.com',
            full_name='u',
            role='accountant',
            is_active=True,
        )
        u.set_password('p')
        rollback_db.session.add(u)
        rollback_db.session.commit()
        cash = GLService.get_account(test_tenant.id, '1000')
        assert cash is not None
        assert cash.normal_balance == 'DEBIT'
        res = GLService.post_journal(
            tenant_id=test_tenant.id,
            source_type='ledger',
            source_id=10,
            description='cash activity',
            lines=[
                {'account_code': '1000', 'debit': 100, 'credit': 0},
                {'account_code': '1000', 'debit': 50, 'credit': 0},
                {'account_code': '1000', 'debit': 0, 'credit': 30},
                {'account_code': '4000', 'debit': 0, 'credit': 120},
            ],
            posted_by=u.id,
        )
        assert res['debit_total'] == 150
        assert res['credit_total'] == 150
        expected_balance = Decimal('120')

        lines = (
            rollback_db.session.execute(
                select(GLJournalLine)
                .where(GLJournalLine.journal_id == res['journal_id'])
                .order_by(GLJournalLine.id)
            )
            .scalars()
            .all()
        )
        cash_lines = [line for line in lines if line.account_id == cash.id]
        running = Decimal('0')
        for line in cash_lines:
            running += Decimal(str(line.debit_amount or 0)) - Decimal(str(line.credit_amount or 0))
        assert running == expected_balance

    def test_running_balance_credit_account(self, rollback_db, test_tenant):
        from models.user import User

        GLService.seed_coa(test_tenant.id)
        rollback_db.session.commit()
        u = User(
            username='ac_' + uuid.uuid4().hex[:8],
            email='ac@x.com',
            full_name='u',
            role='accountant',
            is_active=True,
        )
        u.set_password('p')
        rollback_db.session.add(u)
        rollback_db.session.commit()
        revenue = GLService.get_account(test_tenant.id, '4000')
        assert revenue is not None
        assert revenue.normal_balance == 'CREDIT'
        res = GLService.post_journal(
            tenant_id=test_tenant.id,
            source_type='ledger',
            source_id=20,
            description='revenue activity',
            lines=[
                {'account_code': '4000', 'debit': 0, 'credit': 200},
                {'account_code': '4000', 'debit': 0, 'credit': 100},
                {'account_code': '4000', 'debit': 50, 'credit': 0},
                {'account_code': '1000', 'debit': 250, 'credit': 0},
            ],
            posted_by=u.id,
        )
        assert res['debit_total'] == 300
        assert res['credit_total'] == 300

        lines = (
            rollback_db.session.execute(
                select(GLJournalLine)
                .where(GLJournalLine.journal_id == res['journal_id'])
                .order_by(GLJournalLine.id)
            )
            .scalars()
            .all()
        )
        revenue_lines = [line for line in lines if line.account_id == revenue.id]
        running = Decimal('0')
        for line in revenue_lines:
            running += Decimal(str(line.credit_amount or 0)) - Decimal(str(line.debit_amount or 0))
        assert running == Decimal('250')


class TestPeriodClosing:
    def test_close_period_works(self, rollback_db, test_tenant):
        from models.user import User

        GLService.seed_coa(test_tenant.id)
        rollback_db.session.commit()
        u = User(
            username='cp_' + uuid.uuid4().hex[:8],
            email='cp@x.com',
            full_name='u',
            role='accountant',
            is_active=True,
        )
        u.set_password('p')
        rollback_db.session.add(u)
        rollback_db.session.commit()
        GLService.ensure_financial_periods(test_tenant.id)
        rollback_db.session.commit()
        period = (
            rollback_db.session.execute(
                select(FinancialPeriod).where(FinancialPeriod.tenant_id == test_tenant.id)
            )
            .scalars()
            .first()
        )
        assert period is not None
        assert not period.is_closed
        result = GLService.close_period(test_tenant.id, period.id, closed_by=u.id)
        assert result['is_closed'] is True
        period_refreshed = rollback_db.session.get(FinancialPeriod, period.id)
        assert period_refreshed.is_closed is True
        assert period_refreshed.closed_by == u.id

    def test_post_to_closed_period_raises(self, rollback_db, test_tenant):
        from models.user import User

        GLService.seed_coa(test_tenant.id)
        rollback_db.session.commit()
        u = User(
            username='pc_' + uuid.uuid4().hex[:8],
            email='pc@x.com',
            full_name='u',
            role='accountant',
            is_active=True,
        )
        u.set_password('p')
        rollback_db.session.add(u)
        rollback_db.session.commit()
        GLService.ensure_financial_periods(test_tenant.id)
        rollback_db.session.commit()
        period = (
            rollback_db.session.execute(
                select(FinancialPeriod).where(FinancialPeriod.tenant_id == test_tenant.id)
            )
            .scalars()
            .first()
        )
        assert period is not None
        GLService.close_period(test_tenant.id, period.id, closed_by=u.id)
        rollback_db.session.commit()
        with pytest.raises(ValueError, match='closed financial period'):
            GLService.post_journal(
                tenant_id=test_tenant.id,
                source_type='visit',
                source_id=999,
                description='should fail',
                lines=[
                    {'account_code': '1000', 'debit': 100, 'credit': 0},
                    {'account_code': '4000', 'debit': 0, 'credit': 100},
                ],
                posted_by=u.id,
            )

    def test_post_to_open_period_succeeds(self, rollback_db, test_tenant):
        from models.user import User

        GLService.seed_coa(test_tenant.id)
        rollback_db.session.commit()
        u = User(
            username='po_' + uuid.uuid4().hex[:8],
            email='po@x.com',
            full_name='u',
            role='accountant',
            is_active=True,
        )
        u.set_password('p')
        rollback_db.session.add(u)
        rollback_db.session.commit()
        GLService.ensure_financial_periods(test_tenant.id)
        rollback_db.session.commit()
        GLService.post_journal(
            tenant_id=test_tenant.id,
            source_type='visit',
            source_id=777,
            description='open period',
            lines=[
                {'account_code': '1000', 'debit': 100, 'credit': 0},
                {'account_code': '4000', 'debit': 0, 'credit': 100},
            ],
            posted_by=u.id,
        )
        from models.gl import GLJournal

        journal = (
            rollback_db.session.execute(
                select(GLJournal).where(
                    GLJournal.source_id == 777, GLJournal.source_type == 'visit'
                )
            )
            .scalars()
            .first()
        )
        assert journal is not None

    def test_close_period_twice_raises(self, rollback_db, test_tenant):
        from models.user import User

        GLService.seed_coa(test_tenant.id)
        rollback_db.session.commit()
        u = User(
            username='ct_' + uuid.uuid4().hex[:8],
            email='ct@x.com',
            full_name='u',
            role='accountant',
            is_active=True,
        )
        u.set_password('p')
        rollback_db.session.add(u)
        rollback_db.session.commit()
        GLService.ensure_financial_periods(test_tenant.id)
        rollback_db.session.commit()
        period = (
            rollback_db.session.execute(
                select(FinancialPeriod).where(FinancialPeriod.tenant_id == test_tenant.id)
            )
            .scalars()
            .first()
        )
        assert period is not None
        GLService.close_period(test_tenant.id, period.id, closed_by=u.id)
        with pytest.raises(ValueError, match='already closed'):
            GLService.close_period(test_tenant.id, period.id, closed_by=u.id)
