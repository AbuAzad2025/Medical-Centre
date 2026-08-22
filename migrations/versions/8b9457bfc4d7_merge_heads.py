"""merge_heads

Revision ID: 8b9457bfc4d7
Revises: e8a1c9021b44, p3_002_lab_radiology_audit_cols, p3_003_adt_columns,
         p4_002_drop_queue_payment_status, p5_004_add_controlled_schedule_to_medication
Create Date: 2026-08-21

Proper merge revision unifying the five historical branch heads into a single
lineage so subsequent migrations (p6_*) have one deterministic parent.
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = '8b9457bfc4d7'
down_revision = (
    'e8a1c9021b44',
    'p3_002_lab_radiology_audit_cols',
    'p3_003_adt_columns',
    'p4_002_drop_queue_payment_status',
    'p5_004_add_controlled_schedule_to_medication',
)
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
