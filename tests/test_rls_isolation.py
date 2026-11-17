"""Database-level multi-tenant RLS isolation tests (raw psycopg2, no Flask/SQLAlchemy).

These tests talk to PostgreSQL directly and exercise the row-level-security
policies rather than the application's ``TenantMixin``/``g.tenant_id`` filters.

Important implementation note
-----------------------------
The configured login (``postgres``) is a superuser with ``BYPASSRLS``.  For a
superuser PostgreSQL never evaluates RLS policies (FORCE ROW LEVEL SECURITY
does not change that), so setting ``app.tenant_id`` on such a connection would
*not* enforce isolation.  The fixture therefore idempotently creates and
grants a dedicated non-superuser, NOBYPASSRLS role named ``rls_test_app`` and
every tenant session issues ``SET ROLE rls_test_app`` before setting
``app.tenant_id``.  The effective session identity is asserted explicitly, so
the whole module fails loudly rather than silently bypassing RLS.  The role is
left in place (not dropped) so repeated runs are safe.

All session context (``SET ROLE``, ``app.tenant_id``, ``app.bypass_rls``) is
applied while ``autocommit`` is on, so it survives the rollbacks used by the
WITH CHECK tests.

Graceful skipping
-----------------
The whole module is skipped when the database is unreachable, when the
tenant-scoped tables are missing/altered, or when fewer than two tenants with
patient data have been seeded.  This keeps CI green where the database name or
seed state differs.
"""

from __future__ import annotations

import os
import uuid
from contextlib import contextmanager

import psycopg2
import pytest
from psycopg2 import sql

pytestmark = pytest.mark.db

# Tenant-scoped tables whose isolation is asserted (all carry
# ``tenant_isolation_<table>`` USING + WITH CHECK policies).
TENANT_SCOPED_TABLES = (
    'departments',
    'users',
    'patients',
    'visits',
    'appointments',
    'lab_requests',
    'radiology_requests',
)

# The core tables above have no ``app.bypass_rls`` policy; the super-admin
# bypass path is defined on a handful of audit/form tables.  We use one of
# those (discovered via pg_policies) to verify the bypass behaviour.
BYPASS_TABLE = 'phi_audit_logs'

# Dedicated least-privileged role. Because postgres is a superuser with
# BYPASSRLS, every tenant session must SET ROLE to this account for the
# policies to actually be evaluated.
ROLE_NAME = 'rls_test_app'

RLS_VIOLATION_SQLSTATE = '42501'  # insufficient_privilege / RLS WITH CHECK


def _dsn() -> dict:
    """Connection parameters. Env vars allow CI to point at another database."""
    return {
        'host': os.environ.get('RLS_TEST_DB_HOST', '127.0.0.1'),
        'port': int(os.environ.get('RLS_TEST_DB_PORT', '5433')),
        'user': os.environ.get('RLS_TEST_DB_USER', 'postgres'),
        'password': os.environ.get('RLS_TEST_DB_PASSWORD', 'testpass'),
        'dbname': os.environ.get('RLS_TEST_DB_NAME', 'Medical2026'),
        'connect_timeout': 5,
    }


@contextmanager
def _connect(
    dsn: dict,
    *,
    autocommit: bool = False,
    as_role: str | None = None,
    tenant_id=None,
    bypass: bool = False,
):
    """Yield a raw connection with RLS session context already applied.

    Session settings are committed first (autocommit=True) so that a later
    ``rollback()`` in a test cannot silently strip ``SET ROLE`` /
    ``app.tenant_id`` and invalidate the assertions.
    """
    conn = psycopg2.connect(**dsn)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            if as_role is not None:
                cur.execute(sql.SQL('SET ROLE {}').format(sql.Identifier(as_role)))
            if tenant_id is None:
                cur.execute('RESET app.tenant_id')
            else:
                # Produces: SET app.tenant_id = '1'
                cur.execute('SET app.tenant_id = %s', (str(tenant_id),))
            if bypass:
                cur.execute("SET app.bypass_rls = 'on'")
            else:
                cur.execute('RESET app.bypass_rls')
        conn.autocommit = autocommit
        yield conn
    finally:
        conn.close()


def _count(conn, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(table)))
        return cur.fetchone()[0]


def _count_ids(conn, table: str, ids) -> int:
    ids = list(ids)
    if not ids:
        return 0
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL('SELECT count(*) FROM {} WHERE id = ANY(%s)').format(sql.Identifier(table)),
            (ids,),
        )
        return cur.fetchone()[0]


def _is_rls_violation(exc: psycopg2.Error) -> bool:
    return exc.pgcode == RLS_VIOLATION_SQLSTATE or 'row-level security' in str(exc).lower()


@pytest.fixture(scope='module')
def rls_env():
    """Discover live tenants, snapshot baselines, and create a probe role."""
    dsn = _dsn()

    # 1) Availability + schema + tenant discovery + per-tenant baselines.
    try:
        with _connect(dsn, autocommit=True, bypass=True) as admin:
            with admin.cursor() as cur:
                cur.execute(
                    """
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = ANY(%s)
                    """,
                    (list(TENANT_SCOPED_TABLES),),
                )
                present = {row[0] for row in cur.fetchall()}
                missing = set(TENANT_SCOPED_TABLES) - present
                if missing:
                    pytest.skip(
                        'RLS test tables missing from test database: ' + ', '.join(sorted(missing))
                    )

                cur.execute(
                    """
                    SELECT table_name, column_name FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = ANY(%s)
                      AND column_name IN ('id', 'tenant_id')
                    """,
                    (list(TENANT_SCOPED_TABLES),),
                )
                columns: dict[str, set[str]] = {t: set() for t in TENANT_SCOPED_TABLES}
                for table, column in cur.fetchall():
                    columns[table].add(column)
                for table in TENANT_SCOPED_TABLES:
                    if not {'id', 'tenant_id'} <= columns[table]:
                        pytest.skip(f'Table {table} lacks id/tenant_id columns')

                # Discover tenants from the tenants table (bypass connection),
                # keeping only those that actually have patient data.
                cur.execute(
                    """
                    SELECT t.id
                    FROM tenants t
                    WHERE EXISTS (SELECT 1 FROM patients p WHERE p.tenant_id = t.id)
                    ORDER BY t.id
                    LIMIT 2
                    """
                )
                tenants = [row[0] for row in cur.fetchall()]
                if len(tenants) < 2:
                    pytest.skip(
                        'Fewer than two seeded tenants with patient data; '
                        'cannot exercise cross-tenant isolation'
                    )

                baseline: dict[tuple, int] = {}
                sample_ids: dict[tuple, list] = {}
                for tid in tenants:
                    for table in TENANT_SCOPED_TABLES:
                        cur.execute(
                            sql.SQL('SELECT count(*) FROM {} WHERE tenant_id = %s').format(
                                sql.Identifier(table)
                            ),
                            (tid,),
                        )
                        baseline[(tid, table)] = cur.fetchone()[0]
                        cur.execute(
                            sql.SQL(
                                'SELECT id FROM {} WHERE tenant_id = %s ORDER BY id LIMIT 25'
                            ).format(sql.Identifier(table)),
                            (tid,),
                        )
                        sample_ids[(tid, table)] = [row[0] for row in cur.fetchall()]

                cur.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM pg_policies
                        WHERE schemaname = 'public' AND tablename = %s
                          AND permissive = 'PERMISSIVE'
                          AND (qual ILIKE '%%bypass_rls%%'
                               OR policyname ILIKE '%%super_admin%%')
                    )
                    """,
                    (BYPASS_TABLE,),
                )
                bypass_table = BYPASS_TABLE if cur.fetchone()[0] else None
    except psycopg2.Error as exc:
        pytest.skip(f'PostgreSQL RLS test database unavailable/incompatible: {exc}')

    # 2) Idempotently create (or normalize) the dedicated NON-SUPERUSER role.
    #    It is intentionally left in place so repeated runs are safe.
    try:
        with _connect(dsn, autocommit=True) as admin:
            with admin.cursor() as cur:
                cur.execute(
                    sql.SQL('CREATE ROLE {} NOLOGIN NOSUPERUSER NOBYPASSRLS').format(
                        sql.Identifier(ROLE_NAME)
                    )
                )
    except psycopg2.Error as exc:
        if exc.pgcode != '42710':  # duplicate_object: already exists -> fine
            pytest.skip(f'Cannot create non-superuser RLS role {ROLE_NAME}: {exc}')

    try:
        with _connect(dsn, autocommit=True) as admin:
            with admin.cursor() as cur:
                # Normalize in case a previous run left the role with stronger
                # attributes: it must never be able to bypass RLS.
                cur.execute(
                    sql.SQL(
                        'ALTER ROLE {} NOSUPERUSER NOBYPASSRLS NOCREATEROLE '
                        'NOCREATEDB NOREPLICATION'
                    ).format(sql.Identifier(ROLE_NAME))
                )
                cur.execute(
                    sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(sql.Identifier(ROLE_NAME))
                )
                cur.execute(
                    sql.SQL(
                        'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}'
                    ).format(sql.Identifier(ROLE_NAME))
                )
                cur.execute(
                    sql.SQL('GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO {}').format(
                        sql.Identifier(ROLE_NAME)
                    )
                )
                cur.execute(
                    sql.SQL(
                        'ALTER DEFAULT PRIVILEGES IN SCHEMA public '
                        'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}'
                    ).format(sql.Identifier(ROLE_NAME))
                )
                cur.execute(
                    sql.SQL(
                        'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE ON SEQUENCES TO {}'
                    ).format(sql.Identifier(ROLE_NAME))
                )
    except psycopg2.Error as exc:
        pytest.skip(f'Cannot grant privileges to RLS role {ROLE_NAME}: {exc}')

    # 3) Confirm the effective session really is non-superuser / non-bypassing.
    #    If SET ROLE silently failed, every assertion below would be vacuous.
    with _tenant_conn({'dsn': dsn, 'role': ROLE_NAME}, tenant_id=None) as probe:
        with probe.cursor() as cur:
            cur.execute(
                """
                SELECT current_user,
                       (SELECT rolsuper FROM pg_roles WHERE rolname = current_user),
                       (SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user)
                """
            )
            effective_user, is_super, bypasses_rls = cur.fetchone()
    if effective_user != ROLE_NAME or is_super or bypasses_rls:
        pytest.fail(
            f'RLS probe session is bypassing policies: user={effective_user!r}, '
            f'rolsuper={is_super}, rolbypassrls={bypasses_rls}'
        )

    env = {
        'dsn': dsn,
        'role': ROLE_NAME,
        'tenant_a': tenants[0],
        'tenant_b': tenants[1],
        'baseline': baseline,
        'sample_ids': sample_ids,
        'bypass_table': bypass_table,
    }

    yield env


def _tenant_conn(env, *, tenant_id=None, bypass=False):
    """Shortcut for a connection running as the least-privileged probe role."""
    return _connect(env['dsn'], as_role=env['role'], tenant_id=tenant_id, bypass=bypass)


def test_probe_session_is_non_superuser_and_does_not_bypass_rls(rls_env):
    """Guard against accidentally asserting as a BYPASSRLS superuser."""
    with _tenant_conn(rls_env, tenant_id=None) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT current_user,
                       (SELECT rolsuper FROM pg_roles WHERE rolname = current_user),
                       (SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user)
                """
            )
            effective_user, is_super, bypasses_rls = cur.fetchone()
    assert effective_user == rls_env['role'] == 'rls_test_app'
    assert is_super is False, 'probe role must not be a superuser'
    assert bypasses_rls is False, 'probe role must not have BYPASSRLS'


def test_each_tenant_sees_only_its_own_rows(rls_env):
    """Two tenant connections must see disjoint, tenant-exact row sets."""
    a, b = rls_env['tenant_a'], rls_env['tenant_b']
    with _tenant_conn(rls_env, tenant_id=a) as conn_a, _tenant_conn(rls_env, tenant_id=b) as conn_b:
        for table in TENANT_SCOPED_TABLES:
            seen_a = _count(conn_a, table)
            seen_b = _count(conn_b, table)
            assert seen_a == rls_env['baseline'][(a, table)], (
                f'{table}: tenant {a} sees {seen_a} rows, expected '
                f'{rls_env["baseline"][(a, table)]}'
            )
            assert seen_b == rls_env['baseline'][(b, table)], (
                f'{table}: tenant {b} sees {seen_b} rows, expected '
                f'{rls_env["baseline"][(b, table)]}'
            )

            ids_a = rls_env['sample_ids'][(a, table)]
            ids_b = rls_env['sample_ids'][(b, table)]
            assert not (set(ids_a) & set(ids_b)), f'{table}: sample ids overlap'
            # Rows belonging to B are invisible on A's connection and vice versa.
            assert _count_ids(conn_a, table, ids_b) == 0, (
                f"{table}: tenant {a} can see tenant {b}'s rows"
            )
            assert _count_ids(conn_b, table, ids_a) == 0, (
                f"{table}: tenant {b} can see tenant {a}'s rows"
            )


def test_cross_tenant_department_insert_is_rejected_by_with_check(rls_env):
    """WITH CHECK must reject a row whose tenant_id differs from app.tenant_id."""
    a, b = rls_env['tenant_a'], rls_env['tenant_b']
    suffix = uuid.uuid4().hex[:10]
    bad_name = f'rls-bad-{suffix}'
    good_name = f'rls-good-{suffix}'
    insert_sql = (
        'INSERT INTO departments (name, name_ar, tenant_id, created_at, updated_at) '
        'VALUES (%s, %s, %s, now(), now())'
    )

    with _tenant_conn(rls_env, tenant_id=a) as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(insert_sql, (bad_name, bad_name, b))
        except psycopg2.Error as exc:
            assert _is_rls_violation(exc), (
                f'Expected an RLS WITH CHECK violation, got {exc.pgcode}: {exc}'
            )
        else:
            pytest.fail(
                f'Cross-tenant INSERT (tenant_id={b} while app.tenant_id={a}) was wrongly accepted'
            )
        finally:
            conn.rollback()

        # Positive control proves the same INSERT succeeds for the bound tenant.
        with conn.cursor() as cur:
            cur.execute(insert_sql, (good_name, good_name, a))
            assert cur.rowcount == 1, 'Matching-tenant INSERT should pass WITH CHECK'
        conn.rollback()


def test_select_without_tenant_context_is_fail_closed(rls_env):
    """No app.tenant_id and no bypass => every tenant-scoped SELECT is empty."""
    with _tenant_conn(rls_env, tenant_id=None, bypass=False) as conn:
        for table in TENANT_SCOPED_TABLES:
            seen = _count(conn, table)
            assert seen == 0, (
                f'REAL ISOLATION BUG: {table} has a permissive policy that let a '
                f'non-superuser connection with no app.tenant_id see {seen} rows '
                '(fail-closed requires 0)'
            )


def test_write_without_tenant_context_is_rejected(rls_env):
    """WITH CHECK is also fail-closed when app.tenant_id is unset."""
    name = f'rls-no-ctx-{uuid.uuid4().hex[:10]}'
    with _tenant_conn(rls_env, tenant_id=None, bypass=False) as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    'INSERT INTO departments (name, name_ar, tenant_id, created_at, '
                    'updated_at) VALUES (%s, %s, %s, now(), now())',
                    (name, name, rls_env['tenant_a']),
                )
        except psycopg2.Error as exc:
            assert _is_rls_violation(exc), (
                f'Expected an RLS WITH CHECK violation, got {exc.pgcode}: {exc}'
            )
        else:
            pytest.fail('INSERT with no app.tenant_id was wrongly accepted')
        finally:
            conn.rollback()


def test_bypass_rls_allows_super_admin_cross_tenant_reads(rls_env):
    """app.bypass_rls='on' must allow reads across tenants on a policy that
    defines the super-admin bypass (the core tables do not define one)."""
    table = rls_env['bypass_table']
    if not table:
        pytest.skip('No table with an app.bypass_rls super-admin policy exists')

    a, b = rls_env['tenant_a'], rls_env['tenant_b']
    seeded_ids: list[int] = []
    marker = f'rls-bypass-{uuid.uuid4().hex[:10]}'
    try:
        # Seed one audit row per tenant using the privileged connection.
        with _connect(rls_env['dsn'], autocommit=True, bypass=True) as admin:
            with admin.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM pg_policies
                    WHERE schemaname = 'public' AND tablename = %s
                      AND permissive = 'PERMISSIVE'
                      AND (qual ILIKE '%%bypass_rls%%'
                           OR policyname ILIKE '%%super_admin%%')
                    LIMIT 1
                    """,
                    (table,),
                )
                if cur.fetchone() is None:
                    pytest.skip(f'{table} has no app.bypass_rls policy')

                for offset, tid in enumerate((a, b)):
                    target_id = int(uuid.uuid4().hex[:8], 16) % 1_000_000_000 + offset
                    cur.execute(
                        sql.SQL(
                            'INSERT INTO {} (target_model, target_id, action, tenant_id) '
                            "VALUES (%s, %s, 'CREATE', %s) RETURNING id"
                        ).format(sql.Identifier(table)),
                        (marker, target_id, tid),
                    )
                    seeded_ids.append(cur.fetchone()[0])

        # Without bypass each tenant sees only its own seeded row.
        with (
            _tenant_conn(rls_env, tenant_id=a) as conn_a,
            _tenant_conn(rls_env, tenant_id=b) as conn_b,
        ):
            assert _count_ids(conn_a, table, seeded_ids) == 1, (
                f'tenant {a} should see exactly its own seeded row'
            )
            assert _count_ids(conn_b, table, seeded_ids) == 1, (
                f'tenant {b} should see exactly its own seeded row'
            )

        # With bypass and no tenant binding, both rows become visible.
        with _tenant_conn(rls_env, tenant_id=None, bypass=True) as admin_like:
            visible = _count_ids(admin_like, table, seeded_ids)
            assert visible == 2, (
                f"app.bypass_rls=on should expose both tenants' rows, saw {visible}"
            )
    except psycopg2.Error as exc:
        pytest.skip(f'Cannot exercise app.bypass_rls path on {table}: {exc}')
    finally:
        if seeded_ids:
            try:
                with _connect(rls_env['dsn'], autocommit=True, bypass=True) as admin:
                    with admin.cursor() as cur:
                        cur.execute(
                            sql.SQL('DELETE FROM {} WHERE id = ANY(%s)').format(
                                sql.Identifier(table)
                            ),
                            (seeded_ids,),
                        )
            except psycopg2.Error:
                pass
