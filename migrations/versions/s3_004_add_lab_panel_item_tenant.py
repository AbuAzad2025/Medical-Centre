"""Add tenant_id to lab_test_panel_items and fix RLS.

Revision ID: s3_004_add_lab_panel_item_tenant
Revises: s3_003_fix_gl_rls

Adds tenant_id to the join table lab_test_panel_items which links two
tenant-scoped tables. Backfills from parent panel's tenant_id.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision = 's3_004_add_lab_panel_item_tenant'
down_revision = 's3_003_fix_gl_rls'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    # Add tenant_id if not exists
    op.add_column(
        'lab_test_panel_items',
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True, index=True),
    )
    if bind.dialect.name == 'postgresql':
        # Backfill from parent panel
        op.execute(text("""
            UPDATE lab_test_panel_items AS item
            SET tenant_id = panel.tenant_id
            FROM lab_test_panels AS panel
            WHERE item.panel_id = panel.id
            AND item.tenant_id IS NULL
        """))
        # Also try from test catalog if panel was null
        op.execute(text("""
            UPDATE lab_test_panel_items AS item
            SET tenant_id = cat.tenant_id
            FROM lab_test_catalog AS cat
            WHERE item.test_id = cat.id
            AND item.tenant_id IS NULL
        """))
        op.create_index('ix_lab_test_panel_items_tenant_id', 'lab_test_panel_items', ['tenant_id'])
        op.execute('ALTER TABLE lab_test_panel_items ENABLE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE lab_test_panel_items FORCE ROW LEVEL SECURITY')
        op.execute(text("""
            CREATE POLICY tenant_isolation_lab_test_panel_items ON lab_test_panel_items
            USING (tenant_id = NULLIF(current_setting('app.tenant_id'::text, true), '')::integer)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id'::text, true), '')::integer)
        """))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute(text("DROP POLICY IF EXISTS tenant_isolation_lab_test_panel_items ON lab_test_panel_items"))
        op.execute('ALTER TABLE lab_test_panel_items DISABLE ROW LEVEL SECURITY')
        try:
            op.drop_index('ix_lab_test_panel_items_tenant_id', table_name='lab_test_panel_items')
        except Exception:
            pass
    try:
        op.drop_column('lab_test_panel_items', 'tenant_id')
    except Exception:
        pass
