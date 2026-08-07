"""Phase 3.2: Lab/Radiology cancel & amend audit columns

Revision ID: p3_002_lab_radiology_audit_cols
Revises: s2_009_schema_drift_sync
Create Date: 2026-08-07

"""
from alembic import op
import sqlalchemy as sa


revision = 'p3_002_lab_radiology_audit_cols'
down_revision = 's2_009_schema_drift_sync'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # LabRequest: cancelled_at, cancelled_by
    op.add_column('lab_requests', sa.Column('cancelled_at', sa.TIMESTAMP(), nullable=True))
    op.add_column('lab_requests', sa.Column('cancelled_by', sa.Integer(), nullable=True))

    # RadiologyRequest: cancelled_at, cancelled_by
    op.add_column('radiology_requests', sa.Column('cancelled_at', sa.TIMESTAMP(), nullable=True))
    op.add_column('radiology_requests', sa.Column('cancelled_by', sa.Integer(), nullable=True))

    # LabResult: is_critical, amended_by, amended_at
    op.add_column('lab_results', sa.Column('is_critical', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('lab_results', sa.Column('amended_by', sa.Integer(), nullable=True))
    op.add_column('lab_results', sa.Column('amended_at', sa.TIMESTAMP(), nullable=True))

    # RadiologyResult: is_critical, amended_by, amended_at
    op.add_column('radiology_results', sa.Column('is_critical', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('radiology_results', sa.Column('amended_by', sa.Integer(), nullable=True))
    op.add_column('radiology_results', sa.Column('amended_at', sa.TIMESTAMP(), nullable=True))


def downgrade() -> None:
    op.drop_column('radiology_results', 'amended_at')
    op.drop_column('radiology_results', 'amended_by')
    op.drop_column('radiology_results', 'is_critical')
    op.drop_column('lab_results', 'amended_at')
    op.drop_column('lab_results', 'amended_by')
    op.drop_column('lab_results', 'is_critical')
    op.drop_column('radiology_requests', 'cancelled_by')
    op.drop_column('radiology_requests', 'cancelled_at')
    op.drop_column('lab_requests', 'cancelled_by')
    op.drop_column('lab_requests', 'cancelled_at')