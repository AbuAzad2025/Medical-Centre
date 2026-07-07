#!/usr/bin/env python3
"""Data integrity audit: find and fix rows orphaned with tenant_id=0.

After the S2-001 migration backfilled NULL tenant_id values to the sentinel
value 0, any such rows are orphaned — they don't belong to any real tenant.

This script:
  1. Discovers all tenant-scoped tables (via information_schema)
  2. Reports counts of tenant_id=0 rows per table with sample IDs
  3. Can optionally reassign them to a real tenant or delete them

Usage:
    python scripts/ops/audit_orphaned_tenant_rows.py                  # audit only
    python scripts/ops/audit_orphaned_tenant_rows.py --fix-to 5       # reassign to tenant_id=5
    python scripts/ops/audit_orphaned_tenant_rows.py --delete         # DELETE orphaned rows
    python scripts/ops/audit_orphaned_tenant_rows.py --dry-run        # show what would be done

Requires DATABASE_URL or MIGRATE_DATABASE_URL env var.
"""
from __future__ import annotations

import argparse
import os
import sys

import sqlalchemy as sa

DATABASE_URL = os.environ.get('DATABASE_URL') or os.environ.get('MIGRATE_DATABASE_URL')
if not DATABASE_URL:
    print('FATAL: set DATABASE_URL or MIGRATE_DATABASE_URL')
    sys.exit(1)

# Must match app/shared/tenant_filter.py → _GLOBAL_TENANT_TABLES
GLOBAL_TENANT_TABLES = frozenset({
    'tenants', 'roles', 'permissions', 'role_permissions', 'user_permissions',
    'module_permissions', 'department_permissions',
    'system_configs', 'branding_settings', 'platform_audit_logs',
})

def _get_tenant_scoped_tables(conn) -> list[str]:
    """Discover all public tables with a tenant_id column, excluding global."""
    rows = conn.execute(sa.text("""
        SELECT c.relname
        FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        JOIN information_schema.columns col
          ON col.table_name = c.relname
         AND col.table_schema = 'public'
        WHERE n.nspname = 'public'
          AND c.relkind = 'r'
          AND col.column_name = 'tenant_id'
        ORDER BY c.relname
    """)).fetchall()
    return [row[0] for row in rows if row[0] not in GLOBAL_TENANT_TABLES]


def _count_orphans(conn, table: str) -> tuple[int, list[int]]:
    """Return (count, sample_ids) for rows with tenant_id=0."""
    row = conn.execute(
        sa.text(f"SELECT count(*) FROM {table} WHERE tenant_id = 0")
    ).scalar()
    sample = []
    if row and row > 0:
        sample_rows = conn.execute(
            sa.text(f"SELECT id FROM {table} WHERE tenant_id = 0 LIMIT 10")
        ).fetchall()
        sample = [r[0] for r in sample_rows]
    return row or 0, sample


def _fix_reassign(conn, table: str, target_tenant_id: int) -> int:
    """Reassign orphaned rows to a real tenant_id. Returns affected count."""
    result = conn.execute(
        sa.text(
            f"UPDATE {table} SET tenant_id = :tid WHERE tenant_id = 0"
        ),
        {'tid': target_tenant_id},
    )
    return result.rowcount


def _fix_delete(conn, table: str) -> tuple[int, int]:
    """Delete orphaned rows. Returns (deleted_count, total_before)."""
    before = conn.execute(
        sa.text(f"SELECT count(*) FROM {table} WHERE tenant_id = 0")
    ).scalar() or 0
    if before:
        conn.execute(sa.text(f"DELETE FROM {table} WHERE tenant_id = 0"))
    return before, before


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Audit and fix rows orphaned with tenant_id=0',
    )
    parser.add_argument(
        '--fix-to', type=int, default=None,
        help='Reassign orphaned rows to this tenant_id',
    )
    parser.add_argument(
        '--delete', action='store_true',
        help='DELETE orphaned rows instead of reassigning',
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Show what would be done without making changes',
    )
    args = parser.parse_args()

    if args.fix_to and args.delete:
        print('ERROR: Specify --fix-to OR --delete, not both.')
        return 1

    mode = 'audit'
    target_tid = None
    if args.fix_to:
        mode = f'reassign to tenant_id={args.fix_to}'
        target_tid = args.fix_to
    elif args.delete:
        mode = 'delete'

    engine = sa.create_engine(DATABASE_URL)
    with engine.connect() as conn:
        # Validate target tenant exists if --fix-to
        if target_tid:
            exists = conn.execute(
                sa.text("SELECT 1 FROM tenants WHERE id = :tid"),
                {'tid': target_tid},
            ).scalar()
            if not exists:
                print(f'ERROR: Tenant with id={target_tid} does not exist.')
                return 1

        tables = _get_tenant_scoped_tables(conn)
        total_orphans = 0
        total_fixed = 0
        affected_tables: list[tuple[str, int, list[int]]] = []

        print(f'🔍 Scanning {len(tables)} tenant-scoped tables for tenant_id=0...\n')

        for table in tables:
            count, samples = _count_orphans(conn, table)
            if count:
                affected_tables.append((table, count, samples))
                total_orphans += count
                print(f'  ⚠️  {table}: {count} orphaned row(s)')
                if samples:
                    print(f'       Sample IDs: {samples}')
            else:
                print(f'  ✅ {table}: clean')

        print(f'\n{"=" * 50}')
        if not total_orphans:
            print('✅ No orphaned rows found — data integrity is clean!')
            return 0

        print(f'⚠️  TOTAL: {total_orphans} orphaned row(s) across '
              f'{len(affected_tables)} table(s)')
        print()

        if args.dry_run:
            print(f'🔷 DRY RUN — would {mode} {total_orphans} rows')
            return 0

        if not args.fix_to and not args.delete:
            print('🔶 Audit complete. Use --fix-to <tid> or --delete to remediate.')
            return 1

        # Apply fixes
        for table, count, _ in affected_tables:
            if target_tid:
                n = _fix_reassign(conn, table, target_tid)
                total_fixed += n
                print(f'  ✅ {table}: reassigned {n} rows → tenant_id={target_tid}')
            elif args.delete:
                n_before, n_deleted = _fix_delete(conn, table)
                total_fixed += n_deleted
                print(f'  🗑️  {table}: deleted {n_deleted} rows')

        conn.commit()
        print(f'\n✅ Done: {mode} on {total_fixed} rows across '
              f'{len(affected_tables)} table(s)')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
