"""Add exchange_rates table

Revision ID: add_exchange_rates_2026
Revises: tenant_module_stock_2026
Create Date: 2026-06-12 23:59:00
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_exchange_rates_2026'
down_revision = 'tenant_module_stock_2026'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'exchange_rates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('from_currency', sa.String(8), nullable=False),
        sa.Column('to_currency', sa.String(8), nullable=False),
        sa.Column('buy_rate', sa.Numeric(18, 6), nullable=False),
        sa.Column('sell_rate', sa.Numeric(18, 6), nullable=False),
        sa.Column('effective_date', sa.DateTime(), nullable=False),
        sa.Column('source', sa.String(50), nullable=False, server_default='MANUAL'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("from_currency != to_currency", name='chk_diff_currencies'),
    )
    op.create_index('idx_exchange_currency_pair', 'exchange_rates', ['from_currency', 'to_currency'])
    op.create_index('idx_exchange_effective', 'exchange_rates', ['effective_date'])
    op.create_index('idx_exchange_active', 'exchange_rates', ['is_active'])


def downgrade():
    op.drop_index('idx_exchange_active', table_name='exchange_rates')
    op.drop_index('idx_exchange_effective', table_name='exchange_rates')
    op.drop_index('idx_exchange_currency_pair', table_name='exchange_rates')
    op.drop_table('exchange_rates')
