#!/usr/bin/env python3
"""Audit ORM tenant_id tables against PostgreSQL RLS migrations."""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SKIP_TABLES = {
    'tenants', 'subscription_plans', 'alembic_version',
    'module_definitions', 'notification_rules',
    'roles', 'permissions', 'role_permissions', 'user_permissions',
    'module_permissions', 'department_permissions',
    'system_configs', 'branding_settings', 'system_themes',
    'icd10_codes', 'cpt_codes', 'drg_codes',
    'product_bundles', 'platform_audit_logs',
}


def _parse_skip_tables_from_tenant_filter() -> set[str]:
    path = ROOT / 'app' / 'shared' / 'tenant_filter.py'
    if not path.is_file():
        return set(SKIP_TABLES)
    text = path.read_text(encoding='utf-8', errors='ignore')
    match = re.search(r"return name in \{([^}]+)\}", text, re.DOTALL)
    if not match:
        return set(SKIP_TABLES)
    found = set(re.findall(r"'([^']+)'", match.group(1)))
    return found or set(SKIP_TABLES)


def _collect_orm_tenant_tables() -> set[str]:
    tables: set[str] = set()
    for base in (ROOT / 'models', ROOT / 'app'):
        if not base.is_dir():
            continue
        for path in base.rglob('*.py'):
            try:
                tree = ast.parse(path.read_text(encoding='utf-8', errors='ignore'))
            except SyntaxError:
                continue
            tablename: str | None = None
            has_tenant_id = False
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == '__tablename__':
                            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                                tablename = node.value.value
                if isinstance(node, ast.ClassDef):
                    for item in node.body:
                        if isinstance(item, ast.Assign):
                            for target in item.targets:
                                if isinstance(target, ast.Name) and target.id == 'tenant_id':
                                    has_tenant_id = True
                        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                            if item.target.id == 'tenant_id':
                                has_tenant_id = True
                    for base_node in node.bases:
                        if isinstance(base_node, ast.Name) and base_node.id == 'TenantMixin':
                            has_tenant_id = True
            if tablename and has_tenant_id:
                tables.add(tablename)
    return tables


def _parse_rls_tables_from_migration(path: Path) -> set[str]:
    text = path.read_text(encoding='utf-8', errors='ignore')
    match = re.search(r'RLS_TABLES\s*=\s*\[(.*?)\]', text, re.DOTALL)
    if not match:
        return set()
    return set(re.findall(r"'([^']+)'", match.group(1)))


def _collect_rls_tables() -> set[str]:
    versions = ROOT / 'migrations' / 'versions'
    tables: set[str] = set()
    for path in sorted(versions.glob('s1_*_*.py')):
        tables.update(_parse_rls_tables_from_migration(path))
    return tables


def main() -> int:
    parser = argparse.ArgumentParser(description='Audit tenant_id ORM tables vs RLS migrations')
    parser.add_argument('--report-only', action='store_true', help='Always exit 0; print report only')
    args = parser.parse_args()

    skip = _parse_skip_tables_from_tenant_filter()
    orm_tenant = _collect_orm_tenant_tables()
    rls_tables = _collect_rls_tables()

    scoped = orm_tenant - skip
    already_rls = scoped & rls_tables
    missing_rls = sorted(scoped - rls_tables)
    skip_shared = sorted(orm_tenant & skip)

    print('ALREADY_RLS:', len(already_rls))
    for name in sorted(already_rls):
        print(f'  {name}')
    print('SKIP_SHARED:', len(skip_shared))
    for name in skip_shared:
        print(f'  {name}')
    print('MISSING_RLS:', len(missing_rls))
    for name in missing_rls:
        print(f'  {name}')

    if missing_rls and not args.report_only:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
