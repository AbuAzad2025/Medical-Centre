"""p7_001: make visit_id nullable for standalone walk-in support

Allows Prescription, LabRequest, and RadiologyRequest to be created
directly for a patient WITHOUT requiring an active clinical visit.
This enables Standalone Pharmacy, Standalone Lab, and Standalone
Radiology package tiers.

Revision: p7_001_walk_in_nullable_visit
Revises: p6_004_file_uploads_s3_columns
"""

import sqlalchemy as sa
from alembic import op

revision = 'p7_001_walk_in_nullable_visit'
down_revision = 'p6_004_file_uploads_s3_columns'
branch_labels = None
depends_on = None


def upgrade():
    # prescriptions.visit_id → nullable
    op.alter_column(
        'prescriptions', 'visit_id',
        existing_type=sa.Integer(),
        nullable=True,
    )
    # lab_requests.visit_id → nullable
    op.alter_column(
        'lab_requests', 'visit_id',
        existing_type=sa.Integer(),
        nullable=True,
    )
    # radiology_requests.visit_id → nullable
    op.alter_column(
        'radiology_requests', 'visit_id',
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade():
    # Remove standalone walk-in rows (NULL visit_id) before restoring NOT NULL;
    # sentinel 0 violates FK visits.id, so delete instead.
    op.execute('DELETE FROM prescriptions WHERE visit_id IS NULL')
    op.execute('DELETE FROM lab_requests WHERE visit_id IS NULL')
    op.execute('DELETE FROM radiology_requests WHERE visit_id IS NULL')
    op.alter_column('prescriptions', 'visit_id', existing_type=sa.Integer(), nullable=False)
    op.alter_column('lab_requests', 'visit_id', existing_type=sa.Integer(), nullable=False)
    op.alter_column('radiology_requests', 'visit_id', existing_type=sa.Integer(), nullable=False)
