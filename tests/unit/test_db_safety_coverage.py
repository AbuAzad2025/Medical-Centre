"""Coverage tests for utils.db_safety.py."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from utils.db_safety import safe_commit, safe_rollback, safe_transaction

pytest_plugins = ['tests._isolated_tenant']


class TestDBSafety:
    def test_safe_commit_success(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        result = safe_commit(db.session, error_message='test commit')
        assert result is True

    def test_safe_commit_failure(self, app, db, test_tenant, monkeypatch):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)

        def commit_raises(*a, **k):
            raise RuntimeError('commit failed')

        monkeypatch.setattr(db.session.__class__, 'commit', commit_raises)
        result = safe_commit(db.session, error_message='test commit')
        assert result is False

    def test_safe_commit_reraise(self, app, db, test_tenant, monkeypatch):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)

        def commit_raises(*a, **k):
            raise RuntimeError('commit failed')

        monkeypatch.setattr(db.session.__class__, 'commit', commit_raises)
        with pytest.raises(RuntimeError):
            safe_commit(db.session, error_message='test commit', reraise=True)

    def test_safe_rollback_success(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        # Should not raise
        safe_rollback(db.session, error_message='test rollback')

    def test_safe_transaction_success(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        with safe_transaction(db.session, error_message='test transaction'):
            pass  # No changes, just commit

    def test_safe_transaction_failure(self, app, db, test_tenant, monkeypatch):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)

        def commit_raises(*a, **k):
            raise RuntimeError('commit failed')

        monkeypatch.setattr(db.session.__class__, 'commit', commit_raises)
        with pytest.raises(RuntimeError):
            with safe_transaction(db.session, error_message='test transaction'):
                pass
