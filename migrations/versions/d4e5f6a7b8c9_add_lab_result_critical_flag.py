"""add_lab_result_critical_flag

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-01-21 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('lab_results', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_critical', sa.Boolean(), nullable=False, server_default=sa.text('0')))
        batch_op.create_index(batch_op.f('ix_lab_results_is_critical'), ['is_critical'], unique=False)


def downgrade():
    with op.batch_alter_table('lab_results', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_lab_results_is_critical'))
        batch_op.drop_column('is_critical')

