"""P3-001: Add scoped idempotency support to payments.

Revision ID: p3_001_payment_idempotency
Revises: f0ca021c3e4f
Create Date: 2026-06-22

Note: columns/indexes are included in prod_baseline (f0ca021c3e4f); this revision
is idempotent for databases created from that baseline.
"""
from alembic import op
import sqlalchemy as sa

from migration_utils import column_exists, index_exists


revision = 'p3_001_payment_idempotency'
down_revision = 'f0ca021c3e4f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Alembic default version_num is VARCHAR(32); some revision IDs are longer.
    op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64)")

    if not column_exists('payments', 'idempotency_key'):
        op.add_column('payments', sa.Column('idempotency_key', sa.String(length=64), nullable=True))
    if not column_exists('payments', 'operation_type'):
        op.add_column('payments', sa.Column('operation_type', sa.String(length=32), nullable=True))

    if not index_exists('payments', 'ix_payments_idempotency_key'):
        op.create_index('ix_payments_idempotency_key', 'payments', ['idempotency_key'], unique=False)
    if not index_exists('payments', 'ix_payments_operation_type'):
        op.create_index('ix_payments_operation_type', 'payments', ['operation_type'], unique=False)

    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_payment_idempotency "
        "ON payments (tenant_id, operation_type, idempotency_key) "
        "WHERE idempotency_key IS NOT NULL"
    )


def downgrade() -> None:
    if index_exists('payments', 'idx_payment_idempotency'):
        op.drop_index('idx_payment_idempotency', table_name='payments')
    if index_exists('payments', 'ix_payments_operation_type'):
        op.drop_index('ix_payments_operation_type', table_name='payments')
    if index_exists('payments', 'ix_payments_idempotency_key'):
        op.drop_index('ix_payments_idempotency_key', table_name='payments')
    if column_exists('payments', 'operation_type'):
        op.drop_column('payments', 'operation_type')
    if column_exists('payments', 'idempotency_key'):
        op.drop_column('payments', 'idempotency_key')
