"""add slug column to roles table

Revision ID: add_slug_to_roles_20261113
Revises: s4_006_barcode_scan_log_nullable_registry
Create Date: 2026-11-13

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_slug_to_roles_20261113'
down_revision = 's4_006_barcode_scan_log_nullable_registry'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('roles', sa.Column('slug', sa.String(length=50), nullable=True))
    op.create_unique_constraint('uq_role_tenant_slug', 'roles', ['tenant_id', 'slug'])


def downgrade():
    op.drop_constraint('uq_role_tenant_slug', 'roles', type_='unique')
    op.drop_column('roles', 'slug')
