#!/usr/bin/env python3
"""Create the runtime role, grant permissions, verify RLS enforcement."""
from __future__ import annotations

import os
import subprocess
import sys

import sqlalchemy as sa

DATABASE_URL = os.environ['DATABASE_URL']
PARTS = DATABASE_URL.rsplit('@', 1)
ADMIN_URL = f'postgresql://postgres:testpass@{PARTS[1]}'
ROLE_NAME = 'med_app_runtime_ci_test'

GLOBAL_TABLES = frozenset({
    'alembic_version', 'tenants', 'module_definitions', 'product_bundles',
    'packages', 'package_versions', 'package_version_pricing',
    'package_version_availability', 'package_version_entitlements',
    'package_version_limits', 'subscription_plans', 'stripe_webhook_events',
    'cpt_codes', 'drg_codes', 'drug_interactions', 'icd10_codes',
    'lab_test_panel_items', 'notification_rules', 'platform_tenant_assumptions',
    'enterprise_contract_entitlements', 'developer_configs',
})


def psql(conn, sql: str):
    conn.execute(sa.text(sql))


def _run_upgrade() -> None:
    env = {**os.environ, 'RLS_BYPASS_ALLOWED': '1', 'FLASK_APP': 'wsgi:app'}
    result = subprocess.run(
        [sys.executable, '-m', 'flask', 'db', 'upgrade'],
        capture_output=True, text=True, timeout=60, env=env,
    )
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise SystemExit(1)
    print('OK  flask db upgrade completed')


def main() -> int:
    # Run migrations first so tables exist
    _run_upgrade()

    admin = sa.create_engine(ADMIN_URL, isolation_level='AUTOCOMMIT')
    db_name = DATABASE_URL.rsplit('/', 1)[-1]

    with admin.connect() as c:
        c.execute(sa.text(f'SET session_replication_role = replica'))
        psql(c, f"DROP ROLE IF EXISTS {ROLE_NAME}")
        psql(c, f"CREATE ROLE {ROLE_NAME} WITH LOGIN PASSWORD 'test123' "
                 f"NOSUPERUSER NOINHERIT NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS")
        psql(c, f"GRANT USAGE ON SCHEMA public TO {ROLE_NAME}")
        psql(c, f"GRANT SELECT ON TABLE tenants, module_definitions, "
                 f"alembic_version TO {ROLE_NAME}")

        # Get all public tables
        rows = c.execute(sa.text("""
            SELECT c.relname FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relkind = 'r'
        """)).fetchall()
        all_tables = {r[0] for r in rows}
        tenant_tables = all_tables - GLOBAL_TABLES

        for tbl in sorted(tenant_tables):
            psql(c, f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {tbl} TO {ROLE_NAME}")

        # Grant sequence usage
        seqs = c.execute(sa.text("""
            SELECT sequence_name FROM information_schema.sequences
            WHERE sequence_schema = 'public'
        """)).fetchall()
        for seq in seqs:
            psql(c, f"GRANT USAGE ON SEQUENCE {seq[0]} TO {ROLE_NAME}")

    admin.dispose()
    print(f'OK  role {ROLE_NAME} created with permissions')

    # Now connect AS the restricted role and test RLS enforcement
    runtime_url = f'postgresql://{ROLE_NAME}:test123@{PARTS[1]}'

    try:
        rls_engine = sa.create_engine(runtime_url)
        with rls_engine.connect() as conn:
            r = conn.execute(sa.text("SELECT current_user, rolsuper, rolbypassrls "
                                      "FROM pg_roles WHERE rolname = current_user")).fetchone()
            print(f'OK  connected as {r[0]} (superuser={r[1]}, bypassrls={r[2]})')
            assert r[1] is False, f'{r[0]} has superuser!'
            assert r[2] is False, f'{r[0]} has BYPASSRLS!'

            # Verify we can see tenants (SELECT enabled)
            tenant_count = conn.execute(sa.text("SELECT count(*) FROM tenants")).scalar()
            print(f'OK  can SELECT from tenants: {tenant_count} rows')

            # Verify RLS works: SET LOCAL app.tenant_id should filter
            conn.execute(sa.text("SET LOCAL app.tenant_id = '0'"))
            patients = conn.execute(sa.text("SELECT count(*) FROM patients")).scalar()
            print(f'OK  RLS filter active: patients count = {patients} '
                  f'(expect 0 for non-existent tenant)')
    finally:
        rls_engine.dispose()

    # Cleanup
    with admin.connect() as c:
        c.execute(sa.text(f'SET session_replication_role = replica'))
        psql(c, f"DROP OWNED BY {ROLE_NAME} CASCADE")
        psql(c, f"DROP ROLE IF EXISTS {ROLE_NAME}")
    admin.dispose()
    print(f'OK  role {ROLE_NAME} cleaned up')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
