"""add customer_name to pharmacy_sales

Revision ID: add_customer_name_pharmacy_sales
Revises: add_fk_index_20260619
Create Date: 2026-06-21 00:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'add_cust_name_pharm_sale'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('pharmacy_sales', sa.Column('customer_name', sa.String(200), nullable=True))


def downgrade():
    op.drop_column('pharmacy_sales', 'customer_name')
