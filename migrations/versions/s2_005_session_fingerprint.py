"""Add fingerprint column to SessionLog for device tracking

Revision ID: s2_005_session_fingerprint
Revises: s2_004_encrypt_existing_pii
Create Date: 2026-07-28
"""
from alembic import op
import sqlalchemy as sa

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from migration_utils import column_exists

revision = 's2_005_session_fingerprint'
down_revision = 's2_004_encrypt_existing_pii'
branch_labels = None
depends_on = None


def upgrade():
    if not column_exists('session_logs', 'fingerprint'):
        op.add_column('session_logs', sa.Column('fingerprint', sa.String(length=64), nullable=True, index=True))


def downgrade():
    if column_exists('session_logs', 'fingerprint'):
        op.drop_index('ix_session_logs_fingerprint', table_name='session_logs')
        op.drop_column('session_logs', 'fingerprint')