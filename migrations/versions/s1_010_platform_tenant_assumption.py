"""Create platform_tenant_assumptions table (MC-005)

Revision ID: s1_010_platform_tenant_assumption
Revises: s1_009_audit_action_constraint
Create Date: 2026-07-02

"""
from alembic import op
import sqlalchemy as sa

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from migration_utils import table_exists


revision = 's1_010_platform_tenant_assumption'
down_revision = 's1_009_audit_action_constraint'
branch_labels = None
depends_on = None


def upgrade():
    if table_exists('platform_tenant_assumptions'):
        return

    op.create_table(
        'platform_tenant_assumptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False, index=True),
        sa.Column('assumed_tenant_id', sa.Integer(), nullable=False, index=True),
        sa.Column('assumed_by', sa.Integer(), nullable=True),
        sa.Column('reason', sa.String(500), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_by', sa.Integer(), nullable=True),
        sa.Column('revoke_reason', sa.String(500), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assumed_tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assumed_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['revoked_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_platform_assumption_user_active',
        'platform_tenant_assumptions',
        ['user_id', 'is_active'],
    )


def downgrade():
    op.drop_index('ix_platform_assumption_user_active', table_name='platform_tenant_assumptions')
    op.drop_table('platform_tenant_assumptions')
