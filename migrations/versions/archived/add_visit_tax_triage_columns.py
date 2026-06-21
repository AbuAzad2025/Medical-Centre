"""Add missing tax and triage columns to visits table

Revision ID: add_visit_tax_triage_cols
Revises: add_exchange_rates_2026
Create Date: 2026-06-13
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_visit_tax_triage_cols'
down_revision = 'add_exchange_rates_2026'
branch_labels = None
depends_on = None


def upgrade():
    # Add missing columns to visits table
    op.add_column('visits', sa.Column('triage_level', sa.String(20), nullable=True))
    op.add_column('visits', sa.Column('tax_percent', sa.Numeric(5, 2), nullable=True, server_default='0'))
    op.add_column('visits', sa.Column('tax_amount', sa.Numeric(12, 2), nullable=True, server_default='0'))
    op.add_column('visits', sa.Column('is_tax_inclusive', sa.Boolean(), nullable=True, server_default=sa.text('false')))


def downgrade():
    op.drop_column('visits', 'is_tax_inclusive')
    op.drop_column('visits', 'tax_amount')
    op.drop_column('visits', 'tax_percent')
    op.drop_column('visits', 'triage_level')
