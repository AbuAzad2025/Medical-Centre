"""add_doctor_room_to_users

Revision ID: a0b1c2d3e4f5
Revises: 9c0d1e2f3a4b
Create Date: 2026-01-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a0b1c2d3e4f5'
down_revision = '9c0d1e2f3a4b'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('doctor_room', sa.String(length=50), nullable=True))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('doctor_room')
