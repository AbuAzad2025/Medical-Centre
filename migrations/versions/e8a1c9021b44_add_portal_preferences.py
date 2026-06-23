"""Add portal_preferences to patient_accounts — UX1-006

Revision ID: e8a1c9021b44
Revises: dfdad7fc3407
Create Date: 2026-06-23

"""
from alembic import op
import sqlalchemy as sa


revision = 'e8a1c9021b44'
down_revision = 'dfdad7fc3407'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('patient_accounts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('portal_preferences', sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table('patient_accounts', schema=None) as batch_op:
        batch_op.drop_column('portal_preferences')
