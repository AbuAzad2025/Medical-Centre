"""Add users.preferences JSON — phase 11

Revision ID: p11_001_user_preferences
Revises: p5_001_branding_print_headers
"""
from alembic import op
import sqlalchemy as sa

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from migration_utils import column_exists

revision = 'p11_001_user_preferences'
down_revision = 'p5_001_branding_print_headers'
branch_labels = None
depends_on = None


def upgrade():
    if column_exists('users', 'preferences'):
        return
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('preferences', sa.JSON(), nullable=True))


def downgrade():
    if not column_exists('users', 'preferences'):
        return
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('preferences')
