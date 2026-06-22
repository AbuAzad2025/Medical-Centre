"""P3-006: Add refund request table.

Revision ID: p3_006_refund_request
Revises: p3_004_receipt_relationship_repair
Create Date: 2026-06-22
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'p3_006_refund_request'
down_revision = 'p3_004_receipt_relationship_repair'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'refund_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('payment_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('requested_by', sa.Integer(), nullable=True),
        sa.Column('approved_by', sa.Integer(), nullable=True),
        sa.Column('executed_by', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('requested_at', sa.DateTime(), nullable=False),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('executed_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['payment_id'], ['payments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['requested_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['executed_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('amount > 0', name='chk_refund_amount_positive'),
        sa.CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED', 'EXECUTED')",
            name='chk_refund_status'
        ),
    )
    op.create_index('ix_refund_requests_payment_id', 'refund_requests', ['payment_id'], unique=False)
    op.create_index('ix_refund_requests_status', 'refund_requests', ['status'], unique=False)
    op.create_index('ix_refund_requests_tenant_id', 'refund_requests', ['tenant_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_refund_requests_tenant_id', table_name='refund_requests')
    op.drop_index('ix_refund_requests_status', table_name='refund_requests')
    op.drop_index('ix_refund_requests_payment_id', table_name='refund_requests')
    op.drop_table('refund_requests')
