#!/usr/bin/env python3
"""Verify every tenant-scoped table has RLS enabled and enforced.

Uses dynamic detection via ``information_schema.columns`` to determine
which tables are tenant-scoped (have a ``tenant_id`` column) and which are
global (no ``tenant_id`` column).  This eliminates the hardcoded
``GLOBAL_TABLES`` maintainability hazard.

A minimal platform-level allowlist excludes tables that *do* have a
``tenant_id`` column but are cross-tenant by design (auth tables, tenant
registry, system configs, etc.).
"""

from __future__ import annotations

import os
import sys

import sqlalchemy as sa

DATABASE_URL = os.environ.get('DATABASE_URL', os.environ.get('MIGRATE_DATABASE_URL'))
if not DATABASE_URL:
    print('FATAL: set DATABASE_URL or MIGRATE_DATABASE_URL')
    sys.exit(1)

# Tables that DO have a tenant_id column but are platform-level (no RLS
# expected because they are cross-tenant by design).
PLATFORM_TENANT_TABLES = frozenset(
    {
        'tenants',
        'roles',
        'permissions',
        'role_permissions',
        'user_permissions',
        'module_permissions',
        'department_permissions',
        'system_configs',
        'branding_settings',
        'platform_audit_logs',  # has tenant_id column but is cross-tenant audit trail
    }
)


def _get_public_tables(conn) -> list[tuple[str, bool, bool]]:
    """Return (name, relrowsecurity, relforcerowsecurity) for all public tables."""
    return conn.execute(
        sa.text("""
        SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
        FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind = 'r'
        ORDER BY c.relname
    """)
    ).fetchall()


def _get_tables_with_tenant_id(conn) -> set[str]:
    """Return the set of table names that have a ``tenant_id`` column."""
    rows = conn.execute(
        sa.text("""
        SELECT DISTINCT c.relname
        FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        JOIN information_schema.columns col
          ON col.table_name = c.relname
         AND col.table_schema = 'public'
        WHERE n.nspname = 'public'
          AND c.relkind = 'r'
          AND col.column_name = 'tenant_id'
    """)
    ).fetchall()
    return {row[0] for row in rows}


def main() -> int:
    engine = sa.create_engine(DATABASE_URL)
    with engine.connect() as conn:
        tables = _get_public_tables(conn)
        tables_with_tenant_id = _get_tables_with_tenant_id(conn)

    violations: list[str] = []
    tenant_count = 0
    global_count = 0
    platform_count = 0

    for name, rls, force in tables:
        if name not in tables_with_tenant_id:
            global_count += 1
            continue  # No tenant_id column → inherently global, skip RLS check

        if name in PLATFORM_TENANT_TABLES:
            platform_count += 1
            continue  # Has tenant_id but is platform-level, skip RLS check

        tenant_count += 1
        if not rls:
            violations.append(f'  {name}: RLS DISABLED (has tenant_id column)')
        elif not force:
            violations.append(f'  {name}: RLS enabled but NOT FORCED (has tenant_id column)')

    print(f'Total public tables:            {len(tables)}')
    print(f'  Global (no tenant_id):        {global_count}')
    print(f'  Platform (tenant_id, global): {platform_count}')
    print(f'  Tenant-scoped (checked):      {tenant_count}')
    print()

    if violations:
        print(f'FAIL  {len(violations)} RLS violation(s):')
        for v in violations:
            print(v)
        return 1

    print('OK  all tenant-scoped tables have RLS enabled and enforced')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
