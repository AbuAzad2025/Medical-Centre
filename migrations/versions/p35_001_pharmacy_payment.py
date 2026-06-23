"""Add payment_method to pharmacy_sales — §35 G-122

Revision ID: p35_001_pharmacy_payment
Revises: p11_001_user_preferences
"""
from alembic import op
import sqlalchemy as sa

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from migration_utils import column_exists

revision = 'p35_001_pharmacy_payment'
down_revision = 'p11_001_user_preferences'
branch_labels = None
depends_on = None


def upgrade():
    if not column_exists('pharmacy_sales', 'payment_method'):
        with op.batch_alter_table('pharmacy_sales', schema=None) as batch_op:
            batch_op.add_column(sa.Column('payment_method', sa.String(20), nullable=False, server_default='cash'))
    if not column_exists('pharmacy_sales', 'card_last_digits'):
        with op.batch_alter_table('pharmacy_sales', schema=None) as batch_op:
            batch_op.add_column(sa.Column('card_last_digits', sa.String(4), nullable=True))
    if not column_exists('pharmacy_sales', 'transaction_id'):
        with op.batch_alter_table('pharmacy_sales', schema=None) as batch_op:
            batch_op.add_column(sa.Column('transaction_id', sa.String(80), nullable=True))


def downgrade():
    if column_exists('pharmacy_sales', 'transaction_id'):
        with op.batch_alter_table('pharmacy_sales', schema=None) as batch_op:
            batch_op.drop_column('transaction_id')
    if column_exists('pharmacy_sales', 'card_last_digits'):
        with op.batch_alter_table('pharmacy_sales', schema=None) as batch_op:
            batch_op.drop_column('card_last_digits')
    if column_exists('pharmacy_sales', 'payment_method'):
        with op.batch_alter_table('pharmacy_sales', schema=None) as batch_op:
            batch_op.drop_column('payment_method')
