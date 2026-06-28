"""S1-001: Stripe webhook event idempotency table.

Revision: s1_001_stripe_webhook_idempotency
Revises: s0_005
Create Date: 2026-06-28
"""
from alembic import op
import sqlalchemy as sa

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from migration_utils import table_exists


revision = 's1_001_stripe_webhook_idempotency'
down_revision = 's0_005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    if table_exists('stripe_webhook_events'):
        return
    op.create_table(
        'stripe_webhook_events',
        sa.Column('event_id', sa.String(255), primary_key=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='received'),
        sa.Column('payload_hash', sa.String(64), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('received_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('received', 'processing', 'processed', 'failed')",
            name='chk_stripe_webhook_event_status',
        ),
    )


def downgrade() -> None:
    if not table_exists('stripe_webhook_events'):
        return
    op.drop_table('stripe_webhook_events')
