"""Create order_sets / order_set_items / best_practice_advisories if missing.

The models exist (models/order_set.py) but no migration ever created their
tables: production installations got them from an old ``db.create_all()``
self-heal, a fresh deployment got nothing - the CDS / order-set screens then
500 on first use, and s4_001_rls_order_sets silently skipped the tables
because they were absent (see the table_exists guard in migration_utils).

This migration closes the gap. On databases that already have the tables it is
a no-op for the DDL and only (re)asserts the RLS policy, which is what
s4_001_rls_order_sets intended.

Revision ID: s4_004_order_set_tables
Revises: s4_003_appointment_waitlist
Create Date: 2026-11-08
"""

from alembic import op
import sqlalchemy as sa

from migrations.migration_utils import enable_tenant_rls, table_exists

revision = "s4_004_order_set_tables"
down_revision = "s4_003_appointment_waitlist"
branch_labels = None
depends_on = None

RLS_TABLES = ["order_sets", "order_set_items", "best_practice_advisories"]


def upgrade() -> None:
    if not table_exists("order_sets"):
        op.create_table(
            "order_sets",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("name_ar", sa.String(200), nullable=True),
            sa.Column("description", sa.Text, nullable=True),
            sa.Column("category", sa.String(50), nullable=True),
            sa.Column("diagnosis_code", sa.String(20), nullable=True),
            sa.Column("is_active", sa.Boolean, default=True, nullable=False),
            sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=True),
            sa.Column("updated_at", sa.DateTime, nullable=True),
        )

    if not table_exists("order_set_items"):
        op.create_table(
            "order_set_items",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True),
            sa.Column("order_set_id", sa.Integer, sa.ForeignKey("order_sets.id", ondelete="CASCADE"), nullable=False),
            sa.Column("item_type", sa.String(20), nullable=False),
            sa.Column("item_name", sa.String(200), nullable=False),
            sa.Column("item_code", sa.String(50), nullable=True),
            sa.Column("default_dosage", sa.String(100), nullable=True),
            sa.Column("default_quantity", sa.Integer, default=1),
            sa.Column("default_duration", sa.Integer, default=7),
            sa.Column("is_optional", sa.Boolean, default=False),
            sa.Column("sort_order", sa.Integer, default=0),
        )

    if not table_exists("best_practice_advisories"):
        op.create_table(
            "best_practice_advisories",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("name_ar", sa.String(200), nullable=True),
            sa.Column("description", sa.Text, nullable=True),
            sa.Column("trigger_condition", sa.String(50), nullable=False),
            sa.Column("trigger_value", sa.String(200), nullable=True),
            sa.Column("advisory_type", sa.String(20), default="info"),
            sa.Column("advisory_message", sa.Text, nullable=False),
            sa.Column("advisory_message_ar", sa.Text, nullable=True),
            sa.Column("is_active", sa.Boolean, default=True, nullable=False),
            sa.Column("priority", sa.Integer, default=0),
            sa.Column("created_at", sa.DateTime, nullable=True),
        )

    enable_tenant_rls(RLS_TABLES)


def downgrade() -> None:
    # Tables may pre-date this migration (production self-heal), so only the
    # RLS assertion is owned here; dropping user data on downgrade is wrong.
    from migrations.migration_utils import disable_tenant_rls

    disable_tenant_rls(RLS_TABLES)
