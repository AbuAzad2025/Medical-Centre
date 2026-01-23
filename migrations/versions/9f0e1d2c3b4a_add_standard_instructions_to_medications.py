"""add_standard_instructions_to_medications

Revision ID: 9f0e1d2c3b4a
Revises: 6c1a9b2d4f0e
Create Date: 2026-01-21 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = '9f0e1d2c3b4a'
down_revision = '6c1a9b2d4f0e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('medications', schema=None) as batch_op:
        batch_op.add_column(sa.Column('standard_instructions', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('medications', schema=None) as batch_op:
        batch_op.drop_column('standard_instructions')

