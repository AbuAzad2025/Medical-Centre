"""p6-003: Enable RLS FORCE on api_keys (tenant-scoped).

The api_keys table (p6_002) carries tenant_id via TenantMixin and must be
covered by the same row-level-security regime as every other tenant table,
otherwise scripts/ci/audit_rls_coverage.py flags it as a violation.

Policy follows the s1_012 NULLIF pattern for pooled-connection safety:
    tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer

Revision: p6_003_api_keys_rls
Revises: p6_002_api_keys
"""

from alembic import op

revision = 'p6_003_api_keys_rls'
down_revision = 'p6_002_api_keys'
branch_labels = None
depends_on = None


UPGRADE_SQL = """
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_api_keys ON api_keys
    USING (tenant_id = NULLIF(current_setting('app.tenant_id'::text, true), '')::integer)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id'::text, true), '')::integer);
"""

DOWNGRADE_SQL = """
DROP POLICY IF EXISTS tenant_isolation_api_keys ON api_keys;
ALTER TABLE api_keys NO FORCE ROW LEVEL SECURITY;
ALTER TABLE api_keys DISABLE ROW LEVEL SECURITY;
"""


def upgrade():
    op.execute(UPGRADE_SQL)


def downgrade():
    op.execute(DOWNGRADE_SQL)
