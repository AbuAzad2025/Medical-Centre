"""Add settings JSON column to tenants table

Revision ID: add_tenant_settings_json_20260621
Revises: phase_2_6_composite_tenant_id_indexes
Create Date: 2026-06-21

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = 'add_tenant_settings_json_20260621'
down_revision = 'phase_2_6_composite_tenant_id_indexes'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'tenants',
        sa.Column('settings', JSONB(), nullable=True, server_default=sa.text("'{}'::jsonb"))
    )


def downgrade():
    op.drop_column('tenants', 'settings')
