"""p7_004: RLS FORCE on shift_handovers + consultations (tenant-scoped).

Both tables (p7_002 / p7_003) carry tenant_id via TenantMixin and must be
covered by the same row-level-security regime as every other tenant table,
otherwise scripts/ci/audit_rls_coverage.py fails the build.

Policy follows the s1_012 NULLIF pattern for pooled-connection safety:
    tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer

Revision: p7_004_rls_handover_consult
Revises: p7_003_telemedicine_consultations
"""

from alembic import op

revision = 'p7_004_rls_handover_consult'
down_revision = 'p7_003_telemedicine_consultations'
branch_labels = None
depends_on = None

TABLES = ('shift_handovers', 'consultations')

UPGRADE_SQL = """
ALTER TABLE shift_handovers ENABLE ROW LEVEL SECURITY;
ALTER TABLE shift_handovers FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_shift_handovers ON shift_handovers
    USING (tenant_id = NULLIF(current_setting('app.tenant_id'::text, true), '')::integer)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id'::text, true), '')::integer);

ALTER TABLE consultations ENABLE ROW LEVEL SECURITY;
ALTER TABLE consultations FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation_consultations ON consultations
    USING (tenant_id = NULLIF(current_setting('app.tenant_id'::text, true), '')::integer)
    WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id'::text, true), '')::integer);
"""

DOWNGRADE_SQL = """
DROP POLICY IF EXISTS tenant_isolation_consultations ON consultations;
ALTER TABLE consultations NO FORCE ROW LEVEL SECURITY;
ALTER TABLE consultations DISABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation_shift_handovers ON shift_handovers;
ALTER TABLE shift_handovers NO FORCE ROW LEVEL SECURITY;
ALTER TABLE shift_handovers DISABLE ROW LEVEL SECURITY;
"""


def upgrade():
    op.execute(UPGRADE_SQL)


def downgrade():
    op.execute(DOWNGRADE_SQL)
