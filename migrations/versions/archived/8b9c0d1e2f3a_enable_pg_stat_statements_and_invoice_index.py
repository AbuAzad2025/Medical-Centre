"""enable_pg_stat_statements_and_invoice_index

Revision ID: 8b9c0d1e2f3a
Revises: 7a8b9c0d1e2f
Create Date: 2026-01-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '8b9c0d1e2f3a'
down_revision = '7a8b9c0d1e2f'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind and bind.dialect.name == 'postgresql':
        op.execute('CREATE EXTENSION IF NOT EXISTS pg_stat_statements')
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.create_index('idx_invoice_status_created', ['status', 'created_at'], unique=False)


def downgrade():
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.drop_index('idx_invoice_status_created')
