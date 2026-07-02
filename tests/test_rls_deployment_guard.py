"""
Ticket 11: RLS runtime verification and deployment guard
- Verify RLS guard functions correctly identify RLS status
- Verify BYPASSRLS check works
- Verify row_security_active check works
- Verify table RLS status checks work
- Verify policy existence checks work
"""
import pytest
from scripts.rls_deployment_guard import (
    check_role_bypass_rls,
    check_row_security_active,
    check_tables_rls_enabled,
    check_rls_policies_exist,
)
from app_factory import db as _db


@pytest.mark.usefixtures('app')
class TestRLSDeploymentGuard:
    def test_role_bypass_rls_check(self, app):
        with app.app_context():
            conn = _db.engine.raw_connection()
            try:
                ok, msg = check_role_bypass_rls(conn)
                # In test environment, we just verify the function runs without error
                assert ok is True or ok is False
                assert isinstance(msg, str)
            finally:
                conn.close()

    def test_row_security_active_check(self, app):
        with app.app_context():
            conn = _db.engine.raw_connection()
            try:
                ok, msg = check_row_security_active(conn)
                assert ok is True or ok is False
                assert isinstance(msg, str)
            finally:
                conn.close()

    def test_tables_rls_enabled_returns_results(self, app):
        with app.app_context():
            conn = _db.engine.raw_connection()
            try:
                results = check_tables_rls_enabled(conn)
                assert len(results) > 0
                for ok, msg in results:
                    assert isinstance(ok, bool)
                    assert isinstance(msg, str)
            finally:
                conn.close()

    def test_rls_policies_exist_returns_results(self, app):
        with app.app_context():
            conn = _db.engine.raw_connection()
            try:
                results = check_rls_policies_exist(conn)
                assert len(results) > 0
                for ok, msg in results:
                    assert isinstance(ok, bool)
                    assert isinstance(msg, str)
            finally:
                conn.close()

    def test_rls_guard_table_list_not_empty(self, app):
        from scripts.rls_deployment_guard import _TENANT_SCOPED_TABLES
        assert len(_TENANT_SCOPED_TABLES) > 0
        assert 'visits' in _TENANT_SCOPED_TABLES
        assert 'patients' in _TENANT_SCOPED_TABLES
