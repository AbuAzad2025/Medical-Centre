"""P3-001: Add scoped idempotency support to payments.

Revision ID: p3_001_payment_idempotency
Revises: f0ca021c3e4f
Create Date: 2026-06-22
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'p3_001_payment_idempotency'
down_revision = 'f0ca021c3e4f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Expand-only: add nullable columns first.
    op.add_column('payments', sa.Column('idempotency_key', sa.String(length=64), nullable=True))
    op.add_column('payments', sa.Column('operation_type', sa.String(length=32), nullable=True))

    op.create_index('ix_payments_idempotency_key', 'payments', ['idempotency_key'], unique=False)
    op.create_index('ix_payments_operation_type', 'payments', ['operation_type'], unique=False)

    # Partial unique index: only enforce uniqueness when idempotency_key is set.
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_payment_idempotency "
        "ON payments (tenant_id, operation_type, idempotency_key) "
        "WHERE idempotency_key IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_index('idx_payment_idempotency', table_name='payments')
    op.drop_index('ix_payments_operation_type', table_name='payments')
    op.drop_index('ix_payments_idempotency_key', table_name='payments')
    op.drop_column('payments', 'operation_type')
    op.drop_column('payments', 'idempotency_key')
