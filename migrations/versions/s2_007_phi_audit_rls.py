"""Add RLS policies for phi_audit_logs table

Revision ID: s2_007_phi_audit_rls
Revises: s2_006_expand_patient_name_columns
Create Date: 2026-07-29
"""
from alembic import op
import sqlalchemy as sa

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from migration_utils import table_exists


revision = 's2_007_phi_audit_rls'
down_revision = 's2_006_expand_patient_name_columns'
branch_labels = None
depends_on = None


def upgrade():
    if not table_exists('phi_audit_logs'):
        return

    # Enable RLS on phi_audit_logs (FORCE to make it mandatory)
    op.execute('ALTER TABLE phi_audit_logs ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE phi_audit_logs FORCE ROW LEVEL SECURITY')

    # Policy: tenants can only see their own audit logs (SELECT)
    op.execute('''
        CREATE POLICY phi_audit_logs_tenant_select ON phi_audit_logs
        FOR SELECT USING (tenant_id = current_setting('app.tenant_id')::int)
    ''')

    # Policy: tenants can insert their own audit logs (INSERT)
    op.execute('''
        CREATE POLICY phi_audit_logs_tenant_insert ON phi_audit_logs
        FOR INSERT WITH CHECK (tenant_id = current_setting('app.tenant_id')::int)
    ''')

    # Policy: Prevent UPDATE on audit logs (immutable)
    op.execute('''
        CREATE POLICY phi_audit_logs_no_update ON phi_audit_logs
        FOR UPDATE USING (false)
    ''')

    # Policy: Prevent DELETE on audit logs (immutable)
    op.execute('''
        CREATE POLICY phi_audit_logs_no_delete ON phi_audit_logs
        FOR DELETE USING (false)
    ''')

    # For super_admin / platform_owner, allow full access via bypass
    op.execute('''
        CREATE POLICY phi_audit_logs_super_admin ON phi_audit_logs
        FOR ALL USING (current_setting('app.bypass_rls', true) = 'on')
    ''')


def downgrade():
    if not table_exists('phi_audit_logs'):
        return

    op.execute('DROP POLICY IF EXISTS phi_audit_logs_tenant_select ON phi_audit_logs')
    op.execute('DROP POLICY IF EXISTS phi_audit_logs_tenant_insert ON phi_audit_logs')
    op.execute('DROP POLICY IF EXISTS phi_audit_logs_no_update ON phi_audit_logs')
    op.execute('DROP POLICY IF EXISTS phi_audit_logs_no_delete ON phi_audit_logs')
    op.execute('DROP POLICY IF EXISTS phi_audit_logs_super_admin ON phi_audit_logs')
    op.execute('ALTER TABLE phi_audit_logs DISABLE ROW LEVEL SECURITY')