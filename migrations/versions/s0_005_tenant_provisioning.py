"""S0-005: Tenant provisioning lifecycle columns.

Revision: s0_005
Revises: s0_003_saas_data_contracts
Create Date: 2026-06-22
"""
from alembic import op
import sqlalchemy as sa

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from migration_utils import column_exists, check_constraint_exists


revision = 's0_005'
down_revision = 's0_003_saas_data_contracts'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE tenantstatus ADD VALUE IF NOT EXISTS 'TRIAL'")
    op.execute("ALTER TYPE tenantstatus ADD VALUE IF NOT EXISTS 'CANCELLED'")

    if column_exists('package_versions', 'trial_days') and column_exists('package_versions', 'grace_days'):
        return

    with op.batch_alter_table('package_versions', schema=None) as batch_op:
        if not column_exists('package_versions', 'trial_days'):
            batch_op.add_column(sa.Column('trial_days', sa.Integer(), nullable=False, server_default='0'))
        if not column_exists('package_versions', 'grace_days'):
            batch_op.add_column(sa.Column('grace_days', sa.Integer(), nullable=False, server_default='0'))
        if not check_constraint_exists('package_versions', 'chk_package_version_trial_days_non_negative'):
            batch_op.create_check_constraint('chk_package_version_trial_days_non_negative', 'trial_days >= 0')
        if not check_constraint_exists('package_versions', 'chk_package_version_grace_days_non_negative'):
            batch_op.create_check_constraint('chk_package_version_grace_days_non_negative', 'grace_days >= 0')


def downgrade() -> None:
    if not column_exists('package_versions', 'trial_days'):
        return
    with op.batch_alter_table('package_versions', schema=None) as batch_op:
        if check_constraint_exists('package_versions', 'chk_package_version_grace_days_non_negative'):
            batch_op.drop_constraint('chk_package_version_grace_days_non_negative', type_='check')
        if check_constraint_exists('package_versions', 'chk_package_version_trial_days_non_negative'):
            batch_op.drop_constraint('chk_package_version_trial_days_non_negative', type_='check')
        if column_exists('package_versions', 'grace_days'):
            batch_op.drop_column('grace_days')
        if column_exists('package_versions', 'trial_days'):
            batch_op.drop_column('trial_days')
