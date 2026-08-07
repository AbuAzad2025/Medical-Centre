"""Phase 3.3: ADT columns on visits, admissions, beds

Revision ID: p3_003_adt_columns
Revises: s2_009_schema_drift_sync
Create Date: 2026-08-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = 'p3_003_adt_columns'
down_revision = 's2_009_schema_drift_sync'
branch_labels = None
depends_on = None


def _column_exists(connection, table_name: str, column_name: str) -> bool:
    inspector = inspect(connection)
    cols = [c['name'] for c in inspector.get_columns(table_name)]
    return column_name in cols


def upgrade() -> None:
    conn = op.get_bind()
    
    # visits table - ADT columns
    if not _column_exists(conn, 'visits', 'is_inpatient'):
        op.add_column('visits', sa.Column('is_inpatient', sa.Boolean(), nullable=False, server_default='false'))
    if not _column_exists(conn, 'visits', 'admission_date'):
        op.add_column('visits', sa.Column('admission_date', sa.TIMESTAMP(), nullable=True))
    if not _column_exists(conn, 'visits', 'discharge_date'):
        op.add_column('visits', sa.Column('discharge_date', sa.TIMESTAMP(), nullable=True))
    if not _column_exists(conn, 'visits', 'bed_id'):
        op.add_column('visits', sa.Column('bed_id', sa.Integer(), nullable=True))
    if not _column_exists(conn, 'visits', 'ward_id'):
        op.add_column('visits', sa.Column('ward_id', sa.Integer(), nullable=True))

    # admissions table - ADT columns
    if not _column_exists(conn, 'admissions', 'discharge_type'):
        op.add_column('admissions', sa.Column('discharge_type', sa.String(length=50), nullable=True))
    if not _column_exists(conn, 'admissions', 'length_of_stay'):
        op.add_column('admissions', sa.Column('length_of_stay', sa.Integer(), nullable=True))
    if not _column_exists(conn, 'admissions', 'discharge_datetime'):
        op.add_column('admissions', sa.Column('discharge_datetime', sa.TIMESTAMP(), nullable=True))

    # beds table - ADT columns
    if not _column_exists(conn, 'beds', 'status'):
        op.add_column('beds', sa.Column('status', sa.String(length=20), nullable=False, server_default='AVAILABLE'))
    if not _column_exists(conn, 'beds', 'current_patient_id'):
        op.add_column('beds', sa.Column('current_patient_id', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('beds', 'current_patient_id')
    op.drop_column('beds', 'status')
    op.drop_column('admissions', 'discharge_datetime')
    op.drop_column('admissions', 'length_of_stay')
    op.drop_column('admissions', 'discharge_type')
    op.drop_column('visits', 'ward_id')
    op.drop_column('visits', 'bed_id')
    op.drop_column('visits', 'discharge_date')
    op.drop_column('visits', 'admission_date')
    op.drop_column('visits', 'is_inpatient')