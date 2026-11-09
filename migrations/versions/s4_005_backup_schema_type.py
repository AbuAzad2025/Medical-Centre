"""Add 'schema' to the allowed backup_type values in chk_backup_type.

The backup route accepts a `type` of 'schema' (produces a --schema-only
pg_dump) but the check constraint only permitted full/incremental/
differential, so every schema backup failed at the first commit with
CheckViolation. Add the missing value.

Revision ID: s4_005_backup_schema_type
Revises: s4_004_order_set_tables
Create Date: 2026-11-09
"""

from alembic import op

revision = "s4_005_backup_schema_type"
down_revision = "s4_004_order_set_tables"
branch_labels = None
depends_on = None

OLD = "backup_type IN ('full', 'incremental', 'differential')"
NEW = "backup_type IN ('full', 'incremental', 'differential', 'schema')"


def upgrade() -> None:
    op.execute("ALTER TABLE backups DROP CONSTRAINT IF EXISTS chk_backup_type")
    op.execute(f"ALTER TABLE backups ADD CONSTRAINT chk_backup_type CHECK ({NEW})")


def downgrade() -> None:
    op.execute("ALTER TABLE backups DROP CONSTRAINT IF EXISTS chk_backup_type")
    op.execute(f"ALTER TABLE backups ADD CONSTRAINT chk_backup_type CHECK ({OLD})")
