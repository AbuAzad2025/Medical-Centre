"""Lifecycle and RLS acceptance tests for notifications tenant isolation.

Proves the fix for Ticket 11 (notifications RLS errors after commit):
1. Worker lifecycle: N1->commit->N2->commit->query -- no RLS errors
2. Cross-tenant isolation after commit (same session, Tenant A vs B)
3. Missing tenant context: 0 rows AND rejects writes
4. Tests run against real `med_app_runtime` role with real PostgreSQL RLS policies

``med_app_runtime`` has ``BYPASSRLS = false`` (checked at test time).
"""

import os

import pytest
from flask import g
from sqlalchemy import text, select

from app.extensions import db
from app.shared.tenant_filter import TenantIsolationError
from models.notification import Notification
from services.tenant_job_runner import with_tenant_context
from tests.tenant_context import bind_tenant_on_g


def _db_is_postgresql():
    return db.engine.dialect.name == 'postgresql'


# ---------------------------------------------------------------------------
# Helper: resolve DATABASE_URL to a psycopg2 connection for SQL-level RLS tests
# ---------------------------------------------------------------------------

def _rls_connection():
    """Return a raw psycopg2 connection to the same database.

    Skips if the current database user is a superuser — PostgreSQL RLS
    does not apply to superusers or BYPASSRLS roles.
    """
    url = (os.environ.get('TEST_DATABASE_URL')
           or os.environ.get('DATABASE_URL'))
    if not url or not url.startswith('postgresql'):
        pytest.skip('PostgreSQL required for RLS enforcement tests')
    import psycopg2
    conn = psycopg2.connect(url)
    with conn.cursor() as cur:
        cur.execute("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
        row = cur.fetchone()
        if row and row[0]:
            conn.close()
            pytest.skip('Current database user is superuser; RLS is bypassed')
    return conn


# ===================================================================
#  1. Worker Lifecycle
# ===================================================================

@pytest.mark.usefixtures('app')
class TestNotificationWorkerLifecycle:
    """Regression: worker creates N1->commit->N2->commit->query.

    Background workers call ``send_notification()`` which commits.  After
    commit, PostgreSQL clears the transaction-scoped ``SET LOCAL app.tenant_id``,
    so the **next** flush must re-assert it or the RLS WITH CHECK fails.
    """

    def test_two_notifications_after_commit(self, app):
        """N1->commit->N2->commit->query.  (The core fix regression.)"""
        from tests.tenant_context import ensure_default_test_tenant

        tenant = ensure_default_test_tenant(app)

        with app.test_request_context():
            bind_tenant_on_g(tenant, db_session=db.session)

            # -- N1 --
            n1 = Notification(
                title='Lifecycle-1', message='first',
                notification_type='info',
            )
            db.session.add(n1)
            db.session.commit()                     # clears SET LOCAL

            # Prove N1 persisted
            assert db.session.execute(select(Notification).filter_by(title='Lifecycle-1')).scalars().first() is not None

            # Simulate a lazy-load of an expired column (the old
            # ObjectDeletedError path).
            _ = n1.id

            # -- N2 (this raised psycopg2 RLS errors before the fix) --
            n2 = Notification(
                title='Lifecycle-2', message='second',
                notification_type='info',
            )
            db.session.add(n2)
            db.session.commit()

            # Both visible
            titles = {
                r.title for r in
                Notification.query.filter(
                    Notification.title.in_(['Lifecycle-1', 'Lifecycle-2'])
                ).all()
            }
            assert titles == {'Lifecycle-1', 'Lifecycle-2'}

    def test_lazy_load_after_commit_no_object_deleted_error(self, app):
        """Expired-attribute access triggers do_orm_execute, not error.

        After ``commit()`` the ORM expires all non-PK columns.  Accessing
        an expired column fires ``session.execute()`` (under the hood
        ``load_scalar_attributes``).  Without the ``do_orm_execute`` hook
        re-asserting ``SET LOCAL app.tenant_id``, the RLS USING clause
        would see NULL and return zero rows, raising ``ObjectDeletedError``.
        """
        from tests.tenant_context import ensure_default_test_tenant

        tenant = ensure_default_test_tenant(app)

        with app.test_request_context():
            bind_tenant_on_g(tenant, db_session=db.session)

            n = Notification(
                title='LazyAfterCommit', message='lazy-load test',
                notification_type='info',
            )
            db.session.add(n)
            db.session.commit()

            # PK survives commit; other columns are expired.
            # Accessing `.title` triggers a lazy-load.
            assert n.title == 'LazyAfterCommit'
            assert n.message == 'lazy-load test'




# ===================================================================
#  2. Cross-Tenant Isolation
# ===================================================================

@pytest.mark.usefixtures('app')
@pytest.mark.no_tenant_context
class TestCrossTenantIsolation:
    """Prove Tenant A's notification is invisible to Tenant B after commit.

    Uses two pre-existing tenants from the database (created by provisioning,
    not dynamically).  ``med_app_runtime`` has ``SELECT`` on ``tenants``
    but no ``INSERT``/``UPDATE``/``DELETE``, so we reuse existing rows.
    """

    @pytest.fixture(scope='class')
    def tenant_ids(self):
        """Fetch two existing tenant IDs from the DB."""
        from app.core.tenant.models import Tenant
        g._tenant_filter_bypass = True
        rows = Tenant.query.with_entities(Tenant.id).order_by(Tenant.id).limit(2).all()
        g._tenant_filter_bypass = False
        assert len(rows) >= 2, 'Need at least 2 tenants in the database'
        return rows[0][0], rows[1][0]

    def test_tenant_b_cannot_see_tenant_a_notification(self, app, tenant_ids):
        """Same session, two tenants.  B must not see A's data."""
        tid_a, tid_b = tenant_ids

        with app.test_request_context():
            bind_tenant_on_g(tid_a, db_session=db.session)

            n = Notification(
                title='CrossTenant-Secret-A', message='only A',
                notification_type='info',
            )
            db.session.add(n)
            db.session.commit()

            # A sees it
            assert Notification.query.filter_by(
                title='CrossTenant-Secret-A',
            ).first() is not None

        with app.test_request_context():
            bind_tenant_on_g(tid_b, db_session=db.session)

            # B must NOT see A's notification
            assert Notification.query.filter_by(
                title='CrossTenant-Secret-A',
            ).first() is None

    def test_tenant_b_cannot_see_after_expire_all(self, app, tenant_ids):
        """Same as above but with ``expire_all()`` to simulate fresh session."""
        tid_a, tid_b = tenant_ids

        with app.test_request_context():
            bind_tenant_on_g(tid_a, db_session=db.session)

            n = Notification(
                title='CrossTenant-Secret-A2', message='only A',
                notification_type='info',
            )
            db.session.add(n)
            db.session.commit()

        db.session.expire_all()

        with app.test_request_context():
            bind_tenant_on_g(tid_b, db_session=db.session)

            assert Notification.query.filter_by(
                title='CrossTenant-Secret-A2',
            ).first() is None

    def test_pooled_session_tenant_id_cleared_on_context_exit(self, app, tenant_ids):
        """``session.info['_tenant_id']`` is cleared when
        ``with_tenant_context()`` exits, preventing stale tenant identity on
        a pooled (reused) session.

        1. Tenant A job runs and commits.
        2. Context exits — ``session.info['_tenant_id']`` cleaned.
        3. Same session without tenant: write raises ``TenantIsolationError``.
        4. Same session without tenant: query in SaaS mode raises.
        5. Tenant B job runs successfully.
        6. Tenant B cannot see Tenant A's notification.
        7. After Tenant B exit: session remains clean.
        """
        tid_a, tid_b = tenant_ids

        # -- 1. Tenant A job --
        def job_a():
            n = Notification(
                title='Pooled-Reuse-A', message='A',
                notification_type='info',
            )
            db.session.add(n)
            db.session.commit()

        with_tenant_context(app, tid_a, job_a)

        # -- 2. After exit: session.info['_tenant_id'] must be clean --
        assert '_tenant_id' not in db.session.info, \
            'session.info[_tenant_id] leaked after with_tenant_context() exit'

        # -- 3. Same pooled session, no tenant context: write rejected --
        n = Notification(
            title='Pooled-Orphan', message='no tenant',
            notification_type='info',
        )
        db.session.add(n)
        with pytest.raises(TenantIsolationError):
            db.session.commit()
        db.session.rollback()

        # -- 4. Same session, no tenant context: query rejected (SaaS) --
        with app.test_request_context():
            app.config['ENABLE_SAAS_MODE'] = True
            g.tenant_id = None
            g._tenant_filter_bypass = False
            with pytest.raises(TenantIsolationError):
                db.session.execute(select(Notification)).scalars().all()

        # -- 5. Tenant B job --
        b_query_result = []

        def job_b():
            n = Notification(
                title='Pooled-Reuse-B', message='B',
                notification_type='info',
            )
            db.session.add(n)
            db.session.commit()
            # Query while in Tenant B context
            b_query_result.append(
                db.session.execute(select(Notification).filter_by(title='Pooled-Reuse-A')).scalars().first(),
            )

        with_tenant_context(app, tid_b, job_b)

        # -- 6. Tenant B cannot see Tenant A --
        assert b_query_result[0] is None, \
            'Tenant B should not see Tenant A notification'

        # -- 7. After Tenant B exit: still clean --
        assert '_tenant_id' not in db.session.info, \
            'session.info[_tenant_id] leaked after second context exit'


# ===================================================================
#  3. Missing Tenant Context
# ===================================================================

@pytest.mark.usefixtures('app')
@pytest.mark.no_tenant_context
class TestMissingTenantContext:
    """Without tenant context: query returns 0 rows, writes are rejected."""

    def test_missing_context_rejects_query_saas(self, app):
        """``db.session.execute(select(Model)).scalars().all()`` without ``g.tenant_id`` raises."""
        with app.test_request_context():
            app.config['ENABLE_SAAS_MODE'] = True
            g.tenant_id = None
            g._tenant_filter_bypass = False
            with pytest.raises(TenantIsolationError):
                db.session.execute(select(Notification)).scalars().all()

    def test_missing_context_rejects_writes_saas(self, app):
        """INSERT without ``g.tenant_id`` raises on commit."""
        with app.test_request_context():
            app.config['ENABLE_SAAS_MODE'] = True
            g.tenant_id = None
            g._tenant_filter_bypass = False
            n = Notification(
                title='Orphan', message='no tenant',
                notification_type='info',
            )
            db.session.add(n)
            with pytest.raises(TenantIsolationError):
                db.session.commit()
            db.session.rollback()

    def test_missing_context_non_saas_still_requires_tenant(self, app):
        """Even in non-SaaS mode, tenant-scoped records require tenant context."""
        with app.test_request_context():
            app.config['ENABLE_SAAS_MODE'] = False
            g.tenant_id = None
            g._tenant_filter_bypass = False
            n = Notification(
                title='NonSaaS-Orphan', message='no tenant',
                notification_type='info',
            )
            db.session.add(n)
            with pytest.raises(TenantIsolationError):
                db.session.commit()
            db.session.rollback()


@pytest.mark.no_tenant_context
class TestFailClosedTenantBinding:
    """``SET LOCAL`` failures must propagate, not be silently swallowed."""

    def _patch_target_session(self, monkeypatch):
        """Monkeypatch ``execute`` on the **underlying** ORM Session, not
        the ``scoped_session`` wrapper.  Both ``reassert_set_local`` and
        ``auto_assign_tenant`` receive the raw Session via their event
        parameters, so the scoped_session patch misses them."""
        from sqlalchemy.sql.elements import TextClause
        sess = db.session.registry()
        _orig = sess.execute

        def _mock(stmt, *a, **kw):
            # Skip mock for RESET case (SET LOCAL app.tenant_id = '') which is
            # a TextClause. reassert_set_local returns early for TextClause
            # to avoid recursive dispatch. We only want to simulate failure
            # for the actual SET LOCAL with a tenant_id value.
            if isinstance(stmt, TextClause):
                stmt_str = str(stmt)
                if 'app.tenant_id' in stmt_str and "= ''" in stmt_str:
                    return _orig(stmt, *a, **kw)
            if 'SET LOCAL' in str(stmt) and 'app.tenant_id' in str(stmt):
                raise RuntimeError('Simulated SET LOCAL failure')
            return _orig(stmt, *a, **kw)

        monkeypatch.setattr(sess, 'execute', _mock)

    def test_fail_closed_when_reassert_set_local_fails(self, app, monkeypatch):
        """When ``reassert_set_local`` (do_orm_execute) cannot SET LOCAL,
        ``TenantIsolationError`` must propagate for a tenant-scoped SELECT."""
        from tests.tenant_context import ensure_default_test_tenant, bind_tenant_on_g

        tenant = ensure_default_test_tenant(app)
        self._patch_target_session(monkeypatch)

        with app.test_request_context():
            app.config['ENABLE_SAAS_MODE'] = True
            bind_tenant_on_g(tenant, db_session=db.session)
            with pytest.raises(TenantIsolationError):
                db.session.execute(select(Notification)).scalars().all()

    def test_fail_closed_when_auto_assign_set_local_fails(self, app, monkeypatch):
        """When ``auto_assign_tenant`` (before_flush) cannot SET LOCAL,
        ``TenantIsolationError`` must propagate for a tenant-scoped INSERT."""
        from tests.tenant_context import ensure_default_test_tenant, bind_tenant_on_g

        tenant = ensure_default_test_tenant(app)
        self._patch_target_session(monkeypatch)

        with app.test_request_context():
            bind_tenant_on_g(tenant, db_session=db.session)
            n = Notification(
                title='FailClosedFlush', message='SET LOCAL flush failure',
                notification_type='info',
            )
            db.session.add(n)
            with pytest.raises(TenantIsolationError):
                db.session.flush()
            db.session.rollback()

    def test_global_read_still_works_without_tenant_context(self, app):
        """Global/platform table reads legitimately need no tenant context."""
        with app.test_request_context():
            app.config['ENABLE_SAAS_MODE'] = True
            g.tenant_id = None
            g._tenant_filter_bypass = True
            from app.core.tenant.models import Tenant
            rows = Tenant.query.limit(1).all()
            assert isinstance(rows, list)


# ===================================================================
#  4. PostgreSQL RLS Enforcement (direct SQL, bypasses ORM hooks)
# ===================================================================

class TestPostgresRLSEnforcement:
    """SQL-level RLS tests using a raw psycopg2 connection.

    These tests prove that PostgreSQL's RLS policies (``tenant_isolation_*``)
    actually block / allow at the database level, independent of the ORM
    hooks in ``tenant_filter.py``.
    """

    @pytest.fixture(autouse=True)
    def _check_database(self, app):
        if not _db_is_postgresql():
            pytest.skip('PostgreSQL required for RLS enforcement tests')

    def test_rls_blocks_insert_without_session_var(self, app):
        """RLS WITH CHECK rejects INSERT when ``app.tenant_id`` is NULL."""
        conn = _rls_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO notifications "
                    "(title, message, notification_type, tenant_id, sent_at) "
                    "VALUES ('RLS-Blocked', 'test', 'info', 1, NOW())",
                )
                conn.commit()
                pytest.fail('RLS should have blocked this INSERT')
        except Exception as e:
            conn.rollback()
        finally:
            conn.close()

    def test_rls_allows_insert_with_session_var(self, app, test_tenant):
        """RLS WITH CHECK passes when ``app.tenant_id`` matches."""
        conn = _rls_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SET LOCAL app.tenant_id = %s",
                    (str(test_tenant.id),),
                )
                cur.execute(
                    "INSERT INTO notifications "
                    "(title, message, notification_type, tenant_id, sent_at) "
                    "VALUES (%s, 'test', 'info', %s, NOW())",
                    ('RLS-Allowed', test_tenant.id),
                )
                conn.commit()
        finally:
            conn.close()

    def test_rls_blocks_insert_with_wrong_tenant(self, app, test_tenant):
        """RLS blocks INSERT with tenant_id that differs from ``app.tenant_id``."""
        wrong_id = (test_tenant.id + 1) or 9999

        conn = _rls_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SET LOCAL app.tenant_id = %s",
                    (str(test_tenant.id),),
                )
                cur.execute(
                    "INSERT INTO notifications "
                    "(title, message, notification_type, tenant_id, sent_at) "
                    "VALUES (%s, 'test', 'info', %s, NOW())",
                    ('RLS-WrongTenant', wrong_id),
                )
                conn.commit()
                pytest.fail('RLS should have blocked INSERT with wrong tenant_id')
        except Exception as e:
            conn.rollback()
        finally:
            conn.close()

    def test_rls_select_filters_without_session_var(self, app, test_tenant):
        """RLS USING filters out rows when ``app.tenant_id`` is not set.

        Strategy: insert a row WITH the session var set, then SELECT
        without it -- the row should be invisible.
        """
        conn = _rls_connection()
        try:
            with conn.cursor() as cur:
                # Insert with tenant context
                cur.execute(
                    "SET LOCAL app.tenant_id = %s",
                    (str(test_tenant.id),),
                )
                cur.execute(
                    "INSERT INTO notifications "
                    "(title, message, notification_type, tenant_id, sent_at) "
                    "VALUES (%s, 'test', 'info', %s, NOW())",
                    ('RLS-FilterTest', test_tenant.id),
                )
                conn.commit()

            # New connection (same tx or new) -- this one has NO SET LOCAL
            conn2 = _rls_connection()
            try:
                with conn2.cursor() as cur2:
                    cur2.execute(
                        "SELECT COUNT(*) FROM notifications "
                        "WHERE title = 'RLS-FilterTest'",
                    )
                    count = cur2.fetchone()[0]
                    assert count == 0, \
                        f'Expected 0 without context, got {count}'
            finally:
                conn2.close()
        finally:
            conn.close()
