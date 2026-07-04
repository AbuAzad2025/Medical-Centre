"""S1-012: Fix RLS policy expression for pooled connection safety.

Replaces every tenant_isolation_* policy USING/WITH CHECK expression from:
    (tenant_id = (current_setting('app.tenant_id'::text, true))::integer)
to:
    (tenant_id = NULLIF(current_setting('app.tenant_id'::text, true), '')::integer)

Why: When a connection pool reuses the same PostgreSQL backend after a transaction
that used SET LOCAL app.tenant_id, the setting persists in the session as an empty
string ('') instead of being removed.  current_setting('app.tenant_id', true)
returns '' on the next query, and ''::integer raises
InvalidTextRepresentation — crashing the application.

The NULLIF wrapper converts '' to NULL, NULL::integer yields NULL, and
tenant_id = NULL evaluates as UNKNOWN (no rows returned).  This ensures
graceful RLS enforcement on pooled connections that haven't re-established
context yet.

Revision: s1_012_rls_nullif
Revises: s1_011_rls_with_check
"""
from alembic import op

revision = 's1_012_rls_nullif'
down_revision = 's1_011_rls_with_check'
branch_labels = None
depends_on = None


UPGRADE_SQL = """
DO $$
DECLARE
  pol record;
BEGIN
  FOR pol IN
    SELECT n.nspname AS schema_name, c.relname AS table_name, p.polname,
           pg_get_expr(p.polqual, p.polrelid) AS using_expr,
           pg_get_expr(p.polwithcheck, p.polrelid) AS with_check_expr
    FROM pg_policy p
    JOIN pg_class c ON p.polrelid = c.oid
    JOIN pg_namespace n ON c.relnamespace = n.oid
    WHERE p.polname LIKE 'tenant_isolation_%'
  LOOP
    EXECUTE format(
      'ALTER POLICY %I ON %I.%I USING (tenant_id = NULLIF(current_setting(''app.tenant_id''::text, true), '''')::integer)',
      pol.polname, pol.schema_name, pol.table_name
    );
    EXECUTE format(
      'ALTER POLICY %I ON %I.%I WITH CHECK (tenant_id = NULLIF(current_setting(''app.tenant_id''::text, true), '''')::integer)',
      pol.polname, pol.schema_name, pol.table_name
    );
  END LOOP;
END;
$$;
"""

DOWNGRADE_SQL = """
DO $$
DECLARE
  pol record;
BEGIN
  FOR pol IN
    SELECT n.nspname AS schema_name, c.relname AS table_name, p.polname
    FROM pg_policy p
    JOIN pg_class c ON p.polrelid = c.oid
    JOIN pg_namespace n ON c.relnamespace = n.oid
    WHERE p.polname LIKE 'tenant_isolation_%'
  LOOP
    EXECUTE format(
      'ALTER POLICY %I ON %I.%I USING (tenant_id = (current_setting(''app.tenant_id''::text, true))::integer)',
      pol.polname, pol.schema_name, pol.table_name
    );
    EXECUTE format(
      'ALTER POLICY %I ON %I.%I WITH CHECK (tenant_id = (current_setting(''app.tenant_id''::text, true))::integer)',
      pol.polname, pol.schema_name, pol.table_name
    );
  END LOOP;
END;
$$;
"""


def upgrade():
    op.execute(UPGRADE_SQL)


def downgrade():
    op.execute(DOWNGRADE_SQL)
