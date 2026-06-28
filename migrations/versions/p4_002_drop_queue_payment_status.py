"""P4-002: Drop legacy QueueManagement.payment_status (canonical source: Visit.payment_status).

Revision ID: p4_002_drop_queue_payment_status
Revises: p35_001_pharmacy_payment
Create Date: 2026-06-24
"""
from alembic import op
import sqlalchemy as sa

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from migration_utils import table_exists, column_exists


revision = 'p4_002_drop_queue_payment_status'
down_revision = 'p35_001_pharmacy_payment'
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not table_exists('queue_management'):
        return
    if not column_exists('queue_management', 'payment_status'):
        return

    # Backfill visit payment state from queue tickets before dropping the column.
    op.execute(sa.text("""
        UPDATE visits v
        SET payment_status = q.payment_status
        FROM queue_management q
        WHERE q.visit_id = v.id
          AND q.payment_status IS NOT NULL
          AND q.payment_status <> ''
          AND (v.payment_status IS NULL OR v.payment_status = 'PENDING')
    """))

    with op.batch_alter_table('queue_management', schema=None) as batch_op:
        batch_op.drop_column('payment_status')


def downgrade() -> None:
    if not table_exists('queue_management'):
        return
    if column_exists('queue_management', 'payment_status'):
        return

    with op.batch_alter_table('queue_management', schema=None) as batch_op:
        batch_op.add_column(sa.Column('payment_status', sa.String(length=20), nullable=True))

    op.execute(sa.text("""
        UPDATE queue_management q
        SET payment_status = v.payment_status
        FROM visits v
        WHERE q.visit_id = v.id
          AND v.payment_status IS NOT NULL
    """))
