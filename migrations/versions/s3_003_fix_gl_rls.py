"""Fix GL RLS to use FORCE + NULLIF + WITH CHECK and remove IS NULL bypass.

Revision ID: s3_003_fix_gl_rls
Revises: s3_002_financial_periods

Fixes s3_001 and s3_002 which used ENABLE (not FORCE) and
USING (tenant_id = ...::bigint OR tenant_id IS NULL) which exposes
null-tenant rows cross-tenant and lets table owner bypass RLS.
Now uses tenant_isolation_* naming, NULLIF wrapper for pooled
connections, ::integer, and FORCE + WITH CHECK matching s1_011/s1_012.
Also cleans any sentinel tenant_id=0 rows that violate FK.
"""

import sqlalchemy as sa
from alembic import op

revision = 's3_003_fix_gl_rls'
down_revision = 's3_002_financial_periods'
branch_labels = None
depends_on = None

TABLES = ['accounts', 'gl_journals', 'gl_journal_lines', 'financial_periods']
OLD_POLICIES = {
    'accounts': 'accounts_tenant_policy',
    'gl_journals': 'gl_journals_tenant_policy',
    'gl_journal_lines': 'gl_journal_lines_tenant_policy',
    'financial_periods': 'financial_periods_tenant_policy',
}


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        return
    for table in TABLES:
        old = OLD_POLICIES[table]
        new = f'tenant_isolation_{table}'
        op.execute(f'DROP POLICY IF EXISTS {old} ON {table}')
        op.execute(f'DROP POLICY IF EXISTS {new} ON {table}')
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
        op.execute(
            f"CREATE POLICY {new} ON {table} "
            f"USING (tenant_id = NULLIF(current_setting('app.tenant_id'::text, true), '')::integer) "
            f"WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id'::text, true), '')::integer)"
        )
    # Clean sentinel FK-violating rows (tenant_id=0 has no tenants.id)
    op.execute("DELETE FROM gl_journal_lines WHERE tenant_id = 0")
    op.execute("DELETE FROM gl_journals WHERE tenant_id = 0")
    op.execute("DELETE FROM financial_periods WHERE tenant_id = 0")
    op.execute("DELETE FROM accounts WHERE tenant_id = 0")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != 'postgresql':
        return
    for table in TABLES:
        old = OLD_POLICIES[table]
        new = f'tenant_isolation_{table}'
        op.execute(f'DROP POLICY IF EXISTS {new} ON {table}')
        op.execute(f'DROP POLICY IF EXISTS {old} ON {table}')
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        # Re-create original permissive policy for downgrade compatibility
        op.execute(
            f'CREATE POLICY {old} ON {table} '
            f"USING (tenant_id = current_setting('app.tenant_id', true)::bigint OR tenant_id IS NULL)"
        )
