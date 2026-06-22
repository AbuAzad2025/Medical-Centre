"""S0-005: Tenant provisioning lifecycle columns.

Revision: s0_005
Revises: s0_004
Create Date: 2026-06-22
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 's0_005'
down_revision = 's0_003_saas_data_contracts'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ensure tenant status enum supports trial/cancelled lifecycle states
    op.execute("ALTER TYPE tenantstatus ADD VALUE IF NOT EXISTS 'TRIAL'")
    op.execute("ALTER TYPE tenantstatus ADD VALUE IF NOT EXISTS 'CANCELLED'")

    with op.batch_alter_table('package_versions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('trial_days', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('grace_days', sa.Integer(), nullable=False, server_default='0'))
        batch_op.create_check_constraint('chk_package_version_trial_days_non_negative', 'trial_days >= 0')
        batch_op.create_check_constraint('chk_package_version_grace_days_non_negative', 'grace_days >= 0')


def downgrade() -> None:
    with op.batch_alter_table('package_versions', schema=None) as batch_op:
        batch_op.drop_constraint('chk_package_version_grace_days_non_negative', type_='check')
        batch_op.drop_constraint('chk_package_version_trial_days_non_negative', type_='check')
        batch_op.drop_column('grace_days')
        batch_op.drop_column('trial_days')
