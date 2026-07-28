"""Encrypt existing plaintext PII data using FIELD_ENCRYPTION_KEY

Revision ID: s2_004_encrypt_existing_pii
Revises: s2_003_phi_audit_log
Create Date: 2026-07-28

Migrates existing plaintext values in critical PII/PHI columns to encrypted
ciphertext using the FIELD_ENCRYPTION_KEY env var.  Safe to re-run: rows that
are already encrypted (detected by $enc$ / $gcm$ prefix) are skipped.
"""
import os
import sys
from alembic import op

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from migration_utils import column_exists

revision = 's2_004_encrypt_existing_pii'
down_revision = 's2_003_phi_audit_log'
branch_labels = None
depends_on = None


def upgrade():
    key = os.environ.get('FIELD_ENCRYPTION_KEY', '')
    if not key or len(key) < 16:
        return

    try:
        from services.field_encryption_service import FieldEncryptionService
        svc = FieldEncryptionService(key=key)
    except Exception:
        return

    from app.extensions import db
    app_env = os.environ.get('FLASK_ENV', 'testing')
    if app_env not in ('production', 'staging', 'testing'):
        return

    mappings = [
        ('patients', 'national_id'),
        ('patients', 'first_name'),
        ('patients', 'last_name'),
        ('patients', 'first_name_ar'),
        ('patients', 'last_name_ar'),
        ('patients', 'phone'),
        ('patients', 'address'),
        ('patients', 'insurance_member_number'),
        ('users', 'full_name'),
        ('users', 'phone'),
    ]

    for table, column in mappings:
        if not column_exists(table, column):
            continue
        try:
            result = db.session.execute(
                f"SELECT COUNT(*) FROM {table} WHERE \"{column}\" IS NOT NULL "
                f"AND \"{column}\" <> '' "
                f"AND \"{column}\" NOT LIKE '$enc$%' "
                f"AND \"{column}\" NOT LIKE '$gcm$%'"
            )
            pending = result.scalar()
        except Exception:
            continue

        if pending == 0:
            continue

        try:
            from models.patient import Patient
            from models.user import User

            model = Patient if table == 'patients' else User
            col_obj = getattr(model, column)

            rows = db.session.execute(
                db.select(model).where(
                    col_obj.isnot(None),
                    col_obj != '',
                )
            ).scalars().all()

            encrypted_count = 0
            batch = []
            for row in rows:
                val = getattr(row, column)
                if val and not svc.is_encrypted(val):
                    setattr(row, column, svc.encrypt(val))
                    encrypted_count += 1
                    batch.append(row)
                    if len(batch) >= 500:
                        db.session.commit()
                        batch.clear()
            if batch:
                db.session.commit()
        except Exception as exc:
            db.session.rollback()
            continue


def downgrade():
    pass
