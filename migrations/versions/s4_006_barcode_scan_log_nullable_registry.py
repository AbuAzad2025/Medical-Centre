"""Allow barcode_scan_logs.barcode_registry_id to be NULL.

The barcode scan endpoint records every scan, including the ones that do not
match a registry row: ``routes/barcode_routes.py`` writes a
``verification_result='NOT_FOUND'`` row with ``barcode_registry_id=None`` so
that an unmatched specimen scan leaves an audit trail.

The column was declared NOT NULL, so that insert always raised an
IntegrityError. ``handle_route_errors`` turned it into a redirect to the
dashboard, and the caller never learned that the barcode was unknown -- the
endpoint answered a redirect where it is supposed to answer
``{"success": false, "message": "Barcode not found"}``.

Drop the NOT NULL so the failed-scan audit trail can actually be written.

Revision ID: s4_006_barcode_scan_log_nullable_registry
Revises: s4_005_backup_schema_type
Create Date: 2026-11-11
"""

from alembic import op

revision = "s4_006_barcode_scan_log_nullable_registry"
down_revision = "s4_005_backup_schema_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE barcode_scan_logs "
        "ALTER COLUMN barcode_registry_id DROP NOT NULL"
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM barcode_scan_logs WHERE barcode_registry_id IS NULL"
    )
    op.execute(
        "ALTER TABLE barcode_scan_logs "
        "ALTER COLUMN barcode_registry_id SET NOT NULL"
    )
