"""Sync schema drift between models and migration chain

Revision ID: s2_009_schema_drift_sync
Revises: s2_008_comprehensive_rls_force
Create Date: 2026-07-31

The migration chain had drifted from the current models:

1. ``medications.pregnancy_category`` was never created by any migration,
   so databases built via ``flask db upgrade`` (including production) lack
   the column while ``db.create_all`` (tests) silently created it. Every
   ORM insert into medications failed on migrated databases.

2. Nine ``EncryptedString`` columns were still ``VARCHAR(n)`` in migrated
   databases (ciphertext overflows small varchars at runtime). They are
   widened to ``TEXT`` to match the EncryptedString dialect override.

3. Five foreign keys declared in the models were missing from migrated
   databases. They are added with ``NOT VALID`` so existing production rows
   are not scanned/validated during deployment.

Out of scope (intentionally left):
- 126 ``tenant_id`` nullable diffs: the DB is deliberately STRICTER after
  s2_005 (NOT NULL hardening). Models will be aligned separately.
- Missing secondary indexes (performance-only, no correctness impact).
"""
from alembic import op
import sqlalchemy as sa

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from migration_utils import table_exists, column_exists


revision = 's2_009_schema_drift_sync'
down_revision = 's2_008_comprehensive_rls_force'
branch_labels = None
depends_on = None


# (table, column) encrypted columns widened to TEXT
_ENCRYPTED_TO_TEXT = (
    ('email_messages', 'recipient_email'),
    ('notification_queue', 'recipient'),
    ('online_bookings', 'email'),
    ('online_bookings', 'first_name'),
    ('online_bookings', 'last_name'),
    ('online_bookings', 'national_id'),
    ('online_bookings', 'phone'),
    ('user_mfa_settings', 'totp_secret'),
    ('whatsapp_messages', 'phone_number'),
)

# (constraint_name, table, column, ref_table, ref_column, ondelete)
_MISSING_FKS = (
    ('fk_users_department_id', 'users', 'department_id', 'departments', 'id', 'SET NULL'),
    ('fk_departments_head_doctor_id', 'departments', 'head_doctor_id', 'users', 'id', None),
    ('fk_emar_administrations_prescription_id', 'emar_administrations', 'prescription_id', 'prescriptions', 'id', 'SET NULL'),
    ('fk_emar_administrations_medication_id', 'emar_administrations', 'medication_id', 'medications', 'id', 'SET NULL'),
    ('fk_platform_tenant_assumptions_user_id', 'platform_tenant_assumptions', 'user_id', 'users', 'id', 'CASCADE'),
)

_VARCHAR_LEN = {
    'recipient_email': 200, 'recipient': 200, 'email': 120,
    'first_name': 100, 'last_name': 100, 'national_id': 20,
    'phone': 20, 'totp_secret': 64, 'phone_number': 20,
}


def _constraint_exists(name: str, table: str) -> bool:
    conn = op.get_bind()
    row = conn.execute(sa.text(
        "SELECT 1 FROM pg_constraint WHERE conname = :n"
    ), {'n': name}).fetchone()
    return row is not None


def upgrade():
    # 1. medications.pregnancy_category (the drift that broke migrated DBs)
    if table_exists('medications') and not column_exists('medications', 'pregnancy_category'):
        op.add_column('medications', sa.Column('pregnancy_category', sa.String(10), nullable=True))

    # 2. Widen encrypted columns to TEXT
    for table, column in _ENCRYPTED_TO_TEXT:
        if table_exists(table) and column_exists(table, column):
            op.alter_column(table, column, type_=sa.Text(), existing_nullable=True)

    # 3. Missing FKs (NOT VALID — no scan of existing rows)
    for name, table, column, ref_table, ref_column, ondelete in _MISSING_FKS:
        if not table_exists(table) or not column_exists(table, column):
            continue
        if not table_exists(ref_table):
            continue
        if _constraint_exists(name, table):
            continue
        ondelete_sql = f' ON DELETE {ondelete}' if ondelete else ''
        op.execute(
            f'ALTER TABLE {table} ADD CONSTRAINT {name} '
            f'FOREIGN KEY ({column}) REFERENCES {ref_table} ({ref_column})'
            f'{ondelete_sql} NOT VALID'
        )


def downgrade():
    for name, table, *_ in _MISSING_FKS:
        if table_exists(table) and _constraint_exists(name, table):
            op.execute(f'ALTER TABLE {table} DROP CONSTRAINT {name}')

    for table, column in _ENCRYPTED_TO_TEXT:
        if table_exists(table) and column_exists(table, column):
            op.alter_column(table, column, type_=sa.String(_VARCHAR_LEN[column]), existing_nullable=True)

    if table_exists('medications') and column_exists('medications', 'pregnancy_category'):
        op.drop_column('medications', 'pregnancy_category')
