"""P3-004: Repair Receipt relationship to Payment and add lifecycle status.

Revision ID: p3_004_receipt_relationship_repair
Revises: p3_001_payment_idempotency
Create Date: 2026-06-22
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'p3_004_receipt_relationship_repair'
down_revision = 'p3_001_payment_idempotency'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('receipts', sa.Column('payment_id', sa.Integer(), nullable=True))
    op.add_column('receipts', sa.Column('status', sa.String(length=20), nullable=True))
    op.add_column('receipts', sa.Column('void_reason', sa.Text(), nullable=True))

    op.create_foreign_key(
        'fk_receipts_payment_id_payments',
        'receipts', 'payments',
        ['payment_id'], ['id'],
        ondelete='SET NULL'
    )

    op.create_index('ix_receipts_payment_id', 'receipts', ['payment_id'], unique=False)
    op.create_index('ix_receipts_status', 'receipts', ['status'], unique=False)

    op.create_check_constraint(
        'chk_receipt_status',
        'receipts',
        sa.text("status IN ('issued', 'printed', 'voided')")
    )

    # Default existing rows to 'issued' before enforcing NOT NULL on status.
    op.execute("UPDATE receipts SET status = 'issued' WHERE status IS NULL")

    op.alter_column('receipts', 'status', nullable=False)


def downgrade() -> None:
    op.drop_constraint('chk_receipt_status', 'receipts', type_='check')
    op.drop_index('ix_receipts_status', table_name='receipts')
    op.drop_index('ix_receipts_payment_id', table_name='receipts')
    op.drop_constraint('fk_receipts_payment_id_payments', 'receipts', type_='foreignkey')
    op.drop_column('receipts', 'void_reason')
    op.drop_column('receipts', 'status')
    op.drop_column('receipts', 'payment_id')
