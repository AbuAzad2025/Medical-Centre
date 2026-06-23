"""P3-004: Repair Receipt relationship to Payment and add lifecycle status.

Revision ID: p3_004_receipt_relationship_repair
Revises: p3_001_payment_idempotency
Create Date: 2026-06-22
"""
from alembic import op
import sqlalchemy as sa

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from migration_utils import column_exists, index_exists, fk_exists, check_constraint_exists, table_exists


revision = 'p3_004_receipt_relationship_repair'
down_revision = 'p3_001_payment_idempotency'
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not column_exists('receipts', 'payment_id'):
        op.add_column('receipts', sa.Column('payment_id', sa.Integer(), nullable=True))
    if not column_exists('receipts', 'status'):
        op.add_column('receipts', sa.Column('status', sa.String(length=20), nullable=True))
    if not column_exists('receipts', 'void_reason'):
        op.add_column('receipts', sa.Column('void_reason', sa.Text(), nullable=True))

    if table_exists('payments') and not fk_exists('receipts', 'fk_receipts_payment_id_payments'):
        op.create_foreign_key(
            'fk_receipts_payment_id_payments',
            'receipts', 'payments',
            ['payment_id'], ['id'],
            ondelete='SET NULL'
        )

    if not index_exists('receipts', 'ix_receipts_payment_id'):
        op.create_index('ix_receipts_payment_id', 'receipts', ['payment_id'], unique=False)
    if not index_exists('receipts', 'ix_receipts_status'):
        op.create_index('ix_receipts_status', 'receipts', ['status'], unique=False)

    if not check_constraint_exists('receipts', 'chk_receipt_status'):
        op.create_check_constraint(
            'chk_receipt_status',
            'receipts',
            sa.text("status IN ('issued', 'printed', 'voided')")
        )

    op.execute("UPDATE receipts SET status = 'issued' WHERE status IS NULL")

    # Only enforce NOT NULL if column is still nullable (baseline may already be NOT NULL).
    conn = op.get_bind()
    for col in sa.inspect(conn).get_columns('receipts'):
        if col['name'] == 'status' and col.get('nullable', True):
            op.alter_column('receipts', 'status', nullable=False)
            break


def downgrade() -> None:
    if check_constraint_exists('receipts', 'chk_receipt_status'):
        op.drop_constraint('chk_receipt_status', 'receipts', type_='check')
    if index_exists('receipts', 'ix_receipts_status'):
        op.drop_index('ix_receipts_status', table_name='receipts')
    if index_exists('receipts', 'ix_receipts_payment_id'):
        op.drop_index('ix_receipts_payment_id', table_name='receipts')
    if fk_exists('receipts', 'fk_receipts_payment_id_payments'):
        op.drop_constraint('fk_receipts_payment_id_payments', 'receipts', type_='foreignkey')
    if column_exists('receipts', 'void_reason'):
        op.drop_column('receipts', 'void_reason')
    if column_exists('receipts', 'status'):
        op.drop_column('receipts', 'status')
    if column_exists('receipts', 'payment_id'):
        op.drop_column('receipts', 'payment_id')
