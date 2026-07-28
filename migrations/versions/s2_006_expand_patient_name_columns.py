"""Expand PII/PHI encrypted columns to accommodate ciphertext values

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
    # Patient columns: expand all encrypted PII columns to TEXT
    for col in ['first_name', 'last_name', 'first_name_ar', 'last_name_ar',
                'phone', 'national_id', 'insurance_member_number', 'address']:
        if column_exists('patients', col):
            op.alter_column('patients', col, type_=sa.Text(), nullable=True if col not in ('first_name', 'last_name') else False)

    # User columns: expand all encrypted PII columns to TEXT
    for col in ['full_name', 'phone']:
        if column_exists('users', col):
            op.alter_column('users', col, type_=sa.Text(), nullable=True if col == 'phone' else False)


def downgrade():
    for col in ['address', 'insurance_member_number', 'national_id', 'phone',
                'last_name_ar', 'first_name_ar', 'last_name', 'first_name']:
        if column_exists('patients', col):
            op.alter_column('patients', col, type_=sa.String(length=80 if col in ('first_name', 'last_name') else 20))
    for col in ['phone', 'full_name']:
        if column_exists('users', col):
            op.alter_column('users', col, type_=sa.String(length=20 if col == 'phone' else 120))