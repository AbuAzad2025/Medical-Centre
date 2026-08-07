"""Add controlled substance flags and schedule column to Medication model

Revision ID: p5_004_add_controlled_schedule_to_medication
Revises: p5_001_branding_print_headers

"""

from typing import Sequence
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'p5_004_add_controlled_schedule_to_medication'
down_revision: str | None = 's2_009_schema_drift_sync'


def upgrade() -> None:
    # Add is_controlled column (Boolean, default False, NOT NULL)
    op.add_column('medications', sa.Column('is_controlled', sa.Boolean(), nullable=False, server_default='false'))
    # Add schedule column (String(20), nullable)
    op.add_column('medications', sa.Column('schedule', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('medications', 'schedule')
    op.drop_column('medications', 'is_controlled')