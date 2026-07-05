#!/usr/bin/env python3
"""Verify every tenant-scoped table has RLS enabled and enforced."""
from __future__ import annotations

import os
import sys

import sqlalchemy as sa

DATABASE_URL = os.environ.get('DATABASE_URL', os.environ.get('MIGRATE_DATABASE_URL'))
if not DATABASE_URL:
    print('FATAL: set DATABASE_URL or MIGRATE_DATABASE_URL')
    sys.exit(1)

# Tables that are global / not tenant-scoped
GLOBAL_TABLES = frozenset({
    'alembic_version',
    'tenants',
    'module_definitions',
    'product_bundles',
    'packages',
    'package_versions',
    'package_version_pricing',
    'package_version_availability',
    'package_version_entitlements',
    'package_version_limits',
    'subscription_plans',
    'stripe_webhook_events',
    'cpt_codes',
    'drg_codes',
    'drug_interactions',
    'icd10_codes',
    'lab_test_panel_items',
    'notification_rules',
    'platform_tenant_assumptions',
    'enterprise_contract_entitlements',
    'developer_configs',
})


def main() -> int:
    engine = sa.create_engine(DATABASE_URL)
    with engine.connect() as conn:
        tables = conn.execute(sa.text("""
            SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public'
              AND c.relkind = 'r'
            ORDER BY c.relname
        """)).fetchall()

    violations: list[str] = []
    tenant_count = 0
    for name, rls, force in tables:
        if name in GLOBAL_TABLES:
            continue
        tenant_count += 1
        if not rls:
            violations.append(f'  {name}: RLS DISABLED')
        elif not force:
            violations.append(f'  {name}: RLS enabled but NOT FORCED')

    print(f'Total public tables: {len(tables)}')
    print(f'Global tables excluded: {len([t for t in tables if t[0] in GLOBAL_TABLES])}')
    print(f'Tenant-scoped tables checked: {tenant_count}')
    if violations:
        print(f'FAIL {len(violations)} RLS violation(s):')
        for v in violations:
            print(v)
        return 1
    print('OK  all tenant-scoped tables have RLS enabled and enforced')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
