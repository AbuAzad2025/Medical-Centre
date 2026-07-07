"""S2-001: Enforce tenant_id NOT NULL on all tenant-scoped tables.

Adds a NOT NULL constraint to the tenant_id column for every tenant-scoped
table.  Tables in the global-model allowlist (roles, permissions, system_configs,
branding_settings, etc.) are intentionally excluded — they require nullable
tenant_id for cross-tenant platform operations.

The migration uses dynamic introspection: it queries information_schema.columns
at migration time to find all tables that have a tenant_id column.  This
automatically handles tables created by future migrations *before* this one runs.

Safety: if any rows with NULL tenant_id are found in a target table, they are
backfilled to a sentinel value (0) and a warning is printed.  In a healthy
production system running the tenant isolation layer, there should be zero
such rows.  If unexpected backfills occur, investigate immediately.

Revision: s2_001_tenant_id_not_null
Revises: s1_012_rls_nullif
"""
from alembic import op
from sqlalchemy import text

revision = 's2_001_tenant_id_not_null'
down_revision = 's1_012_rls_nullif'
branch_labels = None
depends_on = None

# Tables that have a tenant_id column but are global / cross-tenant by
# design.  Their tenant_id must remain nullable.
# NOTE: Keep in sync with app/shared/tenant_filter.py → _GLOBAL_TENANT_TABLES
#       and scripts/ci/audit_rls_coverage.py → PLATFORM_TENANT_TABLES
GLOBAL_TENANT_TABLES = frozenset({
    'tenants',
    'roles', 'permissions', 'role_permissions', 'user_permissions',
    'module_permissions', 'department_permissions',
    'system_configs', 'branding_settings',
    'platform_audit_logs',
})


def _get_tenant_scoped_tables() -> list[str]:
    """Return public table names that have a 'tenant_id' column and are
    NOT in the global-table allowlist."""
    conn = op.get_bind()
    rows = conn.execute(
        text("""
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
        """)
    ).fetchall()
    return [row[0] for row in rows if row[0] not in GLOBAL_TENANT_TABLES]


def _backfill_nulls(table: str, conn) -> int:
    """Backfill any NULL tenant_id rows to 0, returning the count.

    Backfilling to 0 (a sentinel that doesn't match any real tenant) is a
    safety measure so the migration doesn't fail on unexpected NULL rows.
    In a properly isolated system this path should never be reached.
    """
    result = conn.execute(
        text(f"UPDATE {table} SET tenant_id = 0 WHERE tenant_id IS NULL")
    )
    return result.rowcount


def upgrade() -> None:
    conn = op.get_bind()
    tables = _get_tenant_scoped_tables()
    total_backfilled = 0

    for table in tables:
        # Safety: backfill any NULL tenant_id before adding NOT NULL
        n = _backfill_nulls(table, conn)
        if n:
            print(
                f"WARNING: Backfilled {n} NULL tenant_id rows in '{table}'"
                f" — review data integrity"
            )
            total_backfilled += n

        # SET NOT NULL is a metadata-only operation on PostgreSQL (after
        # backfill).  Direct SQL avoids Alembic batch mode, which would
        # trigger an unnecessary full table recreation.
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN tenant_id SET NOT NULL"
        )

    if total_backfilled:
        print(
            f"WARNING: Total NULL tenant_id backfills: {total_backfilled}"
            f" — review data integrity immediately"
        )
        print(
            "Rows with tenant_id=0 are orphaned (no tenant FK)."
            " Investigate how they were created."
        )

    print(f"Applied NOT NULL to tenant_id on {len(tables)} tenant-scoped tables")
    if GLOBAL_TENANT_TABLES:
        print(
            f"Skipped {len(GLOBAL_TENANT_TABLES)} global tables (allowlist)"
        )


def downgrade() -> None:
    tables = _get_tenant_scoped_tables()
    for table in tables:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN tenant_id DROP NOT NULL"
        )
    print(f"Removed NOT NULL from tenant_id on {len(tables)} tables")
