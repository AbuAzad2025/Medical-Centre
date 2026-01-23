"""add_radiology_result_critical_flag

Revision ID: b7c8d9e0f1a2
Revises: f6a7b8c9d0e1
Create Date: 2026-01-21 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = 'b7c8d9e0f1a2'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('radiology_results', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_critical', sa.Boolean(), nullable=False, server_default=sa.text('0')))
        batch_op.create_index(batch_op.f('ix_radiology_results_is_critical'), ['is_critical'], unique=False)


def downgrade():
    with op.batch_alter_table('radiology_results', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_radiology_results_is_critical'))
        batch_op.drop_column('is_critical')

