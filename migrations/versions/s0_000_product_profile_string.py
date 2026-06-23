"""S0-000: Make Tenant.product_profile_code a string to support 21 seed profiles.

Revision ID: s0_000_product_profile_string
Revises: p3_006_refund_request
Create Date: 2026-06-22
"""
from alembic import op
import sqlalchemy as sa

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from migration_utils import index_exists, column_exists


revision = 's0_000_product_profile_string'
down_revision = 'p3_006_refund_request'
branch_labels = None
depends_on = None


def upgrade() -> None:
    if not index_exists('tenants', 'ix_tenants_product_profile_code'):
        op.create_index('ix_tenants_product_profile_code', 'tenants', ['product_profile_code'], unique=False)

    if column_exists('tenants', 'product_profile_code'):
        conn = op.get_bind()
        col = next(c for c in sa.inspect(conn).get_columns('tenants') if c['name'] == 'product_profile_code')
        col_type = str(col['type']).upper()
        if 'VARCHAR' not in col_type and 'CHARACTER VARYING' not in col_type:
            op.execute(
                "ALTER TABLE tenants ALTER COLUMN product_profile_code TYPE VARCHAR(40) "
                "USING product_profile_code::text"
            )


def downgrade() -> None:
    if index_exists('tenants', 'ix_tenants_product_profile_code'):
        op.drop_index('ix_tenants_product_profile_code', table_name='tenants')
    if column_exists('tenants', 'product_profile_code'):
        op.execute(
            "ALTER TABLE tenants ALTER COLUMN product_profile_code TYPE VARCHAR(7) "
            "USING product_profile_code::varchar(7)"
        )
