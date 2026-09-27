"""S3-012: Re-assert the NULLIF guard on every tenant_isolation_* policy.

Regression fix. Revision chain context:

* ``s1_012_rls_nullif`` correctly wrapped every ``tenant_isolation_*`` policy
  expression in ``NULLIF(current_setting('app.tenant_id'::text, true), '')::integer``
  so that an empty tenant GUC degrades to "match nothing" instead of raising.
* ``s2_008_comprehensive_rls_force`` runs LATER in the chain and re-created /
  rewrote those same policies using the bare expression
  ``current_setting('app.tenant_id', true)::int`` - silently reverting the
  pooled-connection safety fix on every tenant-scoped table.

Deployed result: 191 of 200 tenant tables carried the unsafe cast.

Why this is fatal, not cosmetic: ``app/shared/tenant_filter.py`` (the
``reassert_set_local`` handler) deliberately issues::

    SET LOCAL app.tenant_id = ''

whenever a request has no tenant context, with the comment "empty string means
'no tenant' and will not match any tenant_id since they're positive ints".
That reasoning is incorrect: ``''::integer`` does not evaluate to a
non-matching value, it raises ``invalid input syntax for type integer: ""``.
The next ORM statement on the same pooled backend therefore fails with
``InvalidTextRepresentation`` and the request returns HTTP 500.

Observed impact on a clean ``flask db upgrade``: ``GET /auth/login`` followed by
``POST /auth/login`` -> 500, i.e. authentication is impossible. The failure is
connection-pool dependent, so it presents as intermittent 5xx rather than as a
schema fault.

``s3_003_fix_gl_rls`` had already applied the NULLIF form to the three GL
tables, and those tables are confirmed to survive an empty GUC - which is the
control that isolates the policy expression as the sole cause.

Fix: re-apply the s1_012 wrapper to every ``tenant_isolation_*`` policy that
lacks it. Idempotent and safe on a live database; it only tightens behaviour
(empty/absent tenant context yields zero rows instead of an error), so no data
becomes newly visible.

Implementation note: this SQL deliberately contains no ``%`` characters and uses
``quote_ident``/``left`` instead of ``format``/``LIKE``, because psycopg2 treats
bare ``%`` in ``op.execute`` SQL as a parameter placeholder.

Revision: s3_012_rls_nullif_reassert
Revises: s3_011_reception_clinic_billing
"""

from alembic import op

revision = 's3_012_rls_nullif_reassert'
down_revision = 's3_011_reception_clinic_billing'
branch_labels = None
depends_on = None

_SAFE = "tenant_id = NULLIF(current_setting('app.tenant_id'::text, true), '')::integer"
_UNSAFE = "tenant_id = (current_setting('app.tenant_id'::text, true))::integer"

# Only policies whose name starts with the tenant_isolation prefix, and (for
# upgrade) only those whose USING expression does not already contain NULLIF.
_SELECT_ALL = """
SELECT n.nspname AS schema_name, c.relname AS table_name, p.polname
FROM pg_policy p
JOIN pg_class c ON p.polrelid = c.oid
JOIN pg_namespace n ON c.relnamespace = n.oid
WHERE left(p.polname, 17) = 'tenant_isolation_'
"""

_SELECT_UNSAFE = _SELECT_ALL + "AND pg_get_expr(p.polqual, p.polrelid) NOT LIKE '%%NULLIF%%'"

_ALTER = """
DO $do$
DECLARE
  pol record;
  expr text;
BEGIN
  expr := {expr_literal};
  FOR pol IN {select_sql}
  LOOP
    EXECUTE 'ALTER POLICY ' || quote_ident(pol.polname)
         || ' ON ' || quote_ident(pol.schema_name) || '.' || quote_ident(pol.table_name)
         || ' USING (' || expr || ')';
    EXECUTE 'ALTER POLICY ' || quote_ident(pol.polname)
         || ' ON ' || quote_ident(pol.schema_name) || '.' || quote_ident(pol.table_name)
         || ' WITH CHECK (' || expr || ')';
  END LOOP;
END;
$do$;
"""


def _sql_literal(value: str) -> str:
    """Render a Python string as a single-quoted PostgreSQL literal."""
    return "'" + value.replace("'", "''") + "'"


def _ddl(select_sql: str, expr: str) -> str:
    return _ALTER.format(select_sql=select_sql, expr_literal=_sql_literal(expr))


def upgrade():
    # The '%%NULLIF%%' above is written pre-escaped: psycopg2 treats a bare '%'
    # in op.execute SQL as a bind placeholder, so it must arrive as '%%'.
    op.execute(_ddl(_SELECT_UNSAFE, _SAFE))


def downgrade():
    op.execute(_ddl(_SELECT_ALL, _UNSAFE))
