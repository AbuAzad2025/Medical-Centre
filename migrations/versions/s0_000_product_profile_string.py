"""S0-000: Make Tenant.product_profile_code a string to support 21 seed profiles.

Revision ID: s0_000_product_profile_string
Revises: p3_006_refund_request
Create Date: 2026-06-22
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 's0_000_product_profile_string'
down_revision = 'p3_006_refund_request'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index('ix_tenants_product_profile_code', 'tenants', ['product_profile_code'], unique=False)
    op.execute(
        "ALTER TABLE tenants ALTER COLUMN product_profile_code TYPE VARCHAR(40) "
        "USING product_profile_code::text"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE tenants ALTER COLUMN product_profile_code TYPE VARCHAR(7) "
        "USING product_profile_code::varchar(7)"
    )
    op.drop_index('ix_tenants_product_profile_code', table_name='tenants')
