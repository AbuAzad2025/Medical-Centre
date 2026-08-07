"""Enable RLS FORCE on specialty_form tables

Revision ID: s2_010_specialty_forms_rls
Revises: s2_009_schema_drift_sync
Create Date: 2026-08-08

"""
from alembic import op
import sqlalchemy as sa

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from migration_utils import table_exists, column_exists


revision = 's2_010_specialty_forms_rls'
down_revision = 's2_009_schema_drift_sync'
branch_labels = None
depends_on = None


SPECIALTY_FORM_TABLES = [
    'specialty_forms',
    'specialty_form_versions',
    'specialty_form_fields',
    'specialty_form_submissions',
]


def upgrade() -> None:
    conn = op.get_bind()
    
    for table in SPECIALTY_FORM_TABLES:
        if not table_exists(table):
            continue
        if not column_exists(table, 'tenant_id'):
            continue
        
        # Enable RLS and FORCE
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
        
        # Create/recreate policy with USING and WITH CHECK
        policy_name = f'tenant_isolation_{table}'
        op.execute(f"DROP POLICY IF EXISTS {policy_name} ON {table}")
        op.execute(
            f"CREATE POLICY {policy_name} ON {table} "
            f"USING (tenant_id = current_setting('app.tenant_id', true)::int) "
            f"WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::int)"
        )
        
        # Super admin bypass
        op.execute(
            f"CREATE POLICY {table}_super_admin ON {table} "
            f"FOR ALL USING (current_setting('app.bypass_rls', true) = 'on')"
        )


def downgrade() -> None:
    for table in SPECIALTY_FORM_TABLES:
        if not table_exists(table):
            continue
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_super_admin ON {table}")
        op.execute(f'ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {table} DISABLE ROW LEVEL SECURITY')