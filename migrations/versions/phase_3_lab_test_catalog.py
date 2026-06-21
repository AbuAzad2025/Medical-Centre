"""
Phase 3: Create LabTestCatalog, LabTestPanel, and LabTestPanelItem tables.

Revision ID: phase_3_lab_test_catalog
Revises: phase_2_6_composite_tenant_id_indexes
Create Date: 2026-06-21
"""
from alembic import op
import sqlalchemy as sa

revision = 'phase_3_lab_test_catalog'
down_revision = 'phase_2_6_composite_tenant_id_indexes'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('lab_test_catalog',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('name_ar', sa.String(length=200), nullable=False),
        sa.Column('name_en', sa.String(length=200), nullable=True),
        sa.Column('category', sa.String(length=50), nullable=False, server_default='other'),
        sa.Column('unit', sa.String(length=40), nullable=True),
        sa.Column('default_reference_range', sa.String(length=120), nullable=True),
        sa.Column('critical_low', sa.String(length=40), nullable=True),
        sa.Column('critical_high', sa.String(length=40), nullable=True),
        sa.Column('price', sa.Numeric(10, 2), nullable=True, server_default='0'),
        sa.Column('preparation_instructions', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('sort_order', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('idx_lab_test_catalog_tenant_code', 'tenant_id', 'code', unique=True)
    )
    op.create_index('idx_lab_test_catalog_category', 'lab_test_catalog', ['category'])
    op.create_index('idx_lab_test_catalog_is_active', 'lab_test_catalog', ['is_active'])

    op.create_table('lab_test_panels',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('name_ar', sa.String(length=200), nullable=False),
        sa.Column('name_en', sa.String(length=200), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('lab_test_panel_items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('panel_id', sa.Integer(), nullable=False),
        sa.Column('test_id', sa.Integer(), nullable=False),
        sa.Column('sort_order', sa.Integer(), nullable=True, server_default='0'),
        sa.ForeignKeyConstraint(['panel_id'], ['lab_test_panels.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['test_id'], ['lab_test_catalog.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('idx_lab_panel_item_unique', 'panel_id', 'test_id', unique=True)
    )
    op.create_index('idx_lab_panel_item_panel_id', 'lab_test_panel_items', ['panel_id'])
    op.create_index('idx_lab_panel_item_test_id', 'lab_test_panel_items', ['test_id'])


def downgrade():
    op.drop_table('lab_test_panel_items')
    op.drop_table('lab_test_panels')
    op.drop_table('lab_test_catalog')
