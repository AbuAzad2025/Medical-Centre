"""S1-002: PostgreSQL Row-Level Security policies for tenant isolation.

Revision: s1_002_tenant_rls_policies
Revises: s1_001_stripe_webhook_idempotency
Create Date: 2026-06-28
"""
from alembic import op

revision = 's1_002_tenant_rls_policies'
down_revision = 's1_001_stripe_webhook_idempotency'
branch_labels = None
depends_on = None

RLS_TABLES = [
    'visits',
    'patients',
    'invoices',
    'payments',
    'appointments',
    'lab_requests',
    'prescriptions',
    'pharmacy_sales',
    'medical_records',
    'queue_management',
    'users',
]


def upgrade() -> None:
    for table in RLS_TABLES:
        policy_name = f'tenant_isolation_{table}'
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
        op.execute(f"DROP POLICY IF EXISTS {policy_name} ON {table}")
        op.execute(
            f"CREATE POLICY {policy_name} ON {table} "
            f"USING (tenant_id = current_setting('app.tenant_id', true)::int)"
        )


def downgrade() -> None:
    for table in RLS_TABLES:
        policy_name = f'tenant_isolation_{table}'
        op.execute(f"DROP POLICY IF EXISTS {policy_name} ON {table}")
        op.execute(f'ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {table} DISABLE ROW LEVEL SECURITY')
