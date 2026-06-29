"""Focused tests for FinancialService expense CRUD paths."""

import uuid
from datetime import date
import types

import pytest

from services.financial_service import FinancialService
from models.user import User


@pytest.fixture
def exp_ctx(rollback_db):
    db = rollback_db

    def user():
        un = 'exp_' + uuid.uuid4().hex[:8]
        u = User(username=un, email=un + '@x.com', full_name='u', role='accountant', is_active=True)
        u.set_password('p')
        db.session.add(u)
        db.session.commit()
        return u

    return types.SimpleNamespace(db=db, user=user)


class TestExpenseCRUD:
    def test_record_and_list_expense(self, exp_ctx):
        u = exp_ctx.user()
        recorded = FinancialService.record_expense('supplies', 75.5, 'office', u.id)
        assert recorded['success'] is True
        assert recorded['expense']['description'] == 'supplies'
        assert recorded['expense']['amount'] == 75.5

        listed = FinancialService.get_expenses()
        assert listed['success'] is True
        ids = [e['id'] for e in listed['expenses']]
        assert recorded['expense']['id'] in ids

    def test_record_with_explicit_date(self, exp_ctx):
        u = exp_ctx.user()
        target = date(2025, 3, 15)
        res = FinancialService.record_expense(
            'rent', 1000, 'facilities', u.id, expense_date=target,
        )
        assert res['success'] is True
        assert res['expense']['expense_date'] == target.isoformat()

    def test_get_expenses_filters_by_category(self, exp_ctx):
        u = exp_ctx.user()
        FinancialService.record_expense('a', 10, 'travel', u.id)
        FinancialService.record_expense('b', 20, 'misc', u.id)
        travel = FinancialService.get_expenses(category='travel')
        assert travel['success'] is True
        assert all(e['category'] == 'travel' for e in travel['expenses'])

    def test_rejects_non_positive_amount(self, exp_ctx):
        u = exp_ctx.user()
        res = FinancialService.record_expense('bad', -5, 'misc', u.id)
        assert res['success'] is False
        assert res['message'] == 'amount_must_be_positive'

    def test_get_expenses_respects_limit(self, exp_ctx):
        u = exp_ctx.user()
        for i in range(5):
            FinancialService.record_expense(f'item {i}', 1 + i, 'misc', u.id)
        res = FinancialService.get_expenses(limit=2)
        assert res['success'] is True
        assert len(res['expenses']) == 2

    def test_get_expenses_handles_query_failure(self, exp_ctx, monkeypatch):
        from unittest.mock import MagicMock
        from models.expense import Expense

        broken = MagicMock()
        broken.order_by.side_effect = RuntimeError('db down')
        monkeypatch.setattr(Expense, 'query', broken, raising=False)
        res = FinancialService.get_expenses()
        assert res['success'] is False
        assert res['expenses'] == []
