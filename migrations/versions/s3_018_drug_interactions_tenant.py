"""S3-018: Make drug_interactions tenant-scoped.

The drug interaction catalogue was global: one row set for every tenant. So an
interaction one clinic recorded was consulted by every other clinic's dispense
screen, and the clinic that recorded it had no way to scope it or withdraw it.

This gives the table a tenant_id, backfills it from the drugs the interaction
is about, and puts it under the same RLS policy as every other tenant-scoped
table.

The tenant of an interaction is the tenant that owns the drugs it names.
Both drugs are the same tenant in normal operation - the catalogue form only
offers the caller's own formulary - so a row whose two drugs belong to
different tenants cannot be attributed to either and is removed rather than
guessed at. A row whose drugs are gone is removed for the same reason: it
would otherwise be an interaction with nothing to be about.

The unique constraint on the drug pair is left as it is. Medication ids are
globally unique and belong to one tenant, so the pair already identifies the
interaction within a tenant, and a constraint that spans tenants would let one
tenant's pair block another's.

Revision: s3_018_drug_interactions_tenant
Revises: s3_017_rbac_catalogue_readable
"""

from alembic import op
from sqlalchemy import text

revision = 's3_018_drug_interactions_tenant'
down_revision = 's3_017_rbac_catalogue_readable'
branch_labels = None
depends_on = None

POLICY_NAME = 'tenant_isolation_drug_interactions'
POLICY_SQL = "(tenant_id = NULLIF(current_setting('app.tenant_id'::text, true), '')::integer)"


def upgrade() -> None:
    conn = op.get_bind()

    # 1. The column. Nullable for now - the backfill below needs to be able to
    #    leave a row alone while it decides what to do with it.
    op.execute('ALTER TABLE drug_interactions ADD COLUMN IF NOT EXISTS tenant_id INTEGER')
    op.execute(
        'ALTER TABLE drug_interactions ADD CONSTRAINT fk_drug_interactions_tenant '
        'FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE'
    )

    # 2. Backfill from the drugs the interaction is about.
    op.execute(
        """
        UPDATE drug_interactions di
        SET tenant_id = ma.tenant_id
        FROM medications ma, medications mb
        WHERE ma.id = di.medication_a_id
          AND mb.id = di.medication_b_id
          AND ma.tenant_id = mb.tenant_id
          AND ma.tenant_id IS NOT NULL
          AND di.tenant_id IS NULL
        """
    )

    # 3. Rows whose two drugs belong to different tenants, or whose drugs are
    #    gone, cannot be attributed to a tenant. Leaving them would mean a
    #    tenant_id of NULL on a table that is about to be NOT NULL, and a
    #    guess would put a clinical rule in the wrong tenant's formulary.
    orphans = conn.execute(
        text('SELECT count(*) FROM drug_interactions WHERE tenant_id IS NULL')
    ).scalar()
    if orphans:
        print(
            f'WARNING: removing {orphans} drug interaction row(s) that could not be '
            'attributed to a tenant - the two drugs named belong to different '
            'tenants, or one of them no longer exists. Review before deploying.'
        )
        op.execute('DELETE FROM drug_interactions WHERE tenant_id IS NULL')

    # 4. NOT NULL, and the index the tenant filter's predicate needs.
    op.execute('ALTER TABLE drug_interactions ALTER COLUMN tenant_id SET NOT NULL')
    op.execute(
        'CREATE INDEX IF NOT EXISTS ix_drug_interactions_tenant_id ON drug_interactions (tenant_id)'
    )

    # 5. The policy, in the same shape as every other tenant-scoped table.
    op.execute('ALTER TABLE drug_interactions ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE drug_interactions FORCE ROW LEVEL SECURITY')
    op.execute(f'DROP POLICY IF EXISTS {POLICY_NAME} ON drug_interactions')
    op.execute(
        f'CREATE POLICY {POLICY_NAME} ON drug_interactions '
        f'USING {POLICY_SQL} WITH CHECK {POLICY_SQL}'
    )


def downgrade() -> None:
    op.execute(f'DROP POLICY IF EXISTS {POLICY_NAME} ON drug_interactions')
    op.execute('ALTER TABLE drug_interactions NO FORCE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE drug_interactions DISABLE ROW LEVEL SECURITY')
    op.execute('DROP INDEX IF EXISTS ix_drug_interactions_tenant_id')
    op.execute(
        'ALTER TABLE drug_interactions DROP CONSTRAINT IF EXISTS fk_drug_interactions_tenant'
    )
    op.execute('ALTER TABLE drug_interactions DROP COLUMN IF EXISTS tenant_id')
