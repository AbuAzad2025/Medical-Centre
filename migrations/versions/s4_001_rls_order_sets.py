"""Enable RLS on order_sets, order_set_items, best_practice_advisories.

Revision ID: s4_001_rls_order_sets
Revises: d3b694bf1104
Create Date: 2026-11-05
"""

from alembic import op

from migrations.migration_utils import enable_tenant_rls

revision = "s4_001_rls_order_sets"
down_revision = "d3b694bf1104"
branch_labels = None
depends_on = None

RLS_TABLES = ["order_sets", "order_set_items", "best_practice_advisories"]


def upgrade() -> None:
    enable_tenant_rls(RLS_TABLES)


def downgrade() -> None:
    from migrations.migration_utils import disable_tenant_rls

    disable_tenant_rls(RLS_TABLES)