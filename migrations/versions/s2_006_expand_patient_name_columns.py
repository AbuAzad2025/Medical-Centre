"""Expand patient name columns to accommodate encrypted values

Revision ID: s2_006_expand_patient_name_columns
Revises: s2_005_session_fingerprint
Create Date: 2026-07-28
"""
from alembic import op
import sqlalchemy as sa

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from migration_utils import column_exists

revision = 's2_006_expand_patient_name_columns'
down_revision = 's2_005_session_fingerprint'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('patients', 'first_name',
                    type_=sa.String(length=280),
                    existing_type=sa.String(length=160),
                    nullable=False)
    op.alter_column('patients', 'last_name',
                    type_=sa.String(length=280),
                    existing_type=sa.String(length=160),
                    nullable=False)
    op.alter_column('patients', 'first_name_ar',
                    type_=sa.String(length=280),
                    existing_type=sa.String(length=160),
                    nullable=True)
    op.alter_column('patients', 'last_name_ar',
                    type_=sa.String(length=280),
                    existing_type=sa.String(length=160),
                    nullable=True)


def downgrade():
    op.alter_column('patients', 'last_name_ar',
                    type_=sa.String(length=160),
                    existing_type=sa.String(length=280),
                    nullable=True)
    op.alter_column('patients', 'first_name_ar',
                    type_=sa.String(length=160),
                    existing_type=sa.String(length=280),
                    nullable=True)
    op.alter_column('patients', 'last_name',
                    type_=sa.String(length=160),
                    existing_type=sa.String(length=280),
                    nullable=False)
    op.alter_column('patients', 'first_name',
                    type_=sa.String(length=160),
                    existing_type=sa.String(length=280),
                    nullable=False)