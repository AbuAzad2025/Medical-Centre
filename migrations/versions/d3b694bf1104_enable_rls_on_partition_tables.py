"""Enable RLS FORCE on partition tables (_default partitions)

Revision ID: d3b694bf1104
Revises: s3_023_db_performance
Create Date: 2026-11-02 02:03:09.077212

"""
from alembic import op
import sqlalchemy as sa

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from migration_utils import table_exists, column_exists


revision = 'd3b694bf1104'
down_revision = 's3_023_db_performance'
branch_labels = None
depends_on = None


# Partition tables (_default partitions) that need RLS FORCE
# These are default partitions of partitioned tables that have tenant_id
PARTITION_TABLES = [
    'audit_trails_default',
    'login_attempts_default',
    'phi_audit_logs_default',
    'platform_audit_logs_default',
    'security_events_default',
    'slow_query_reports_default',
    'system_logs_default',
]


def upgrade() -> None:
    """Enable RLS FORCE on partition tables with tenant_id"""
    for table in PARTITION_TABLES:
        if not table_exists(table):
            continue
        if not column_exists(table, 'tenant_id'):
            continue
        
        # Enable RLS and FORCE it
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
        
        # Ensure policy exists with USING and WITH CHECK
        policy_name = f'tenant_isolation_{table}'
        op.execute(f"DROP POLICY IF EXISTS {policy_name} ON {table}")
        op.execute(
            f"CREATE POLICY tenant_isolation_{table} ON {table} "
            f"USING (tenant_id = current_setting('app.tenant_id', true)::int) "
            f"WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::int)"
        )


def downgrade() -> None:
    for table in PARTITION_TABLES:
        if not table_exists(table):
            continue
        policy_name = f'tenant_isolation_{table}'
        op.execute(f"DROP POLICY IF EXISTS {policy_name} ON {table}")
        op.execute(f'ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {table} DISABLE ROW LEVEL SECURITY')