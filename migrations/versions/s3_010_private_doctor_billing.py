"""Add billing to private_doctor_clinic for solo dentist self-billing.

Revision ID: s3_010_private_doctor_billing
Revises: s3_009_pending_financial_settlement
"""

import json

import sqlalchemy as sa
from alembic import op

revision = 's3_010_private_doctor_billing'
down_revision = 's3_009_pending_financial_settlement'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    result = bind.execute(
        sa.text("SELECT id, modules FROM product_bundles WHERE slug = 'private_doctor_clinic'")
    )
    row = result.fetchone()
    if row is None:
        return
    bundle_id, modules_raw = row[0], row[1]
    try:
        modules = (
            json.loads(modules_raw) if isinstance(modules_raw, str) else list(modules_raw or [])
        )
    except Exception:
        modules = []
    if 'billing' not in modules:
        modules.append('billing')
        # Keep canonical order: doctor, billing, appointments
        order = ['doctor', 'billing', 'appointments']
        modules = sorted(modules, key=lambda m: order.index(m) if m in order else 99)
        bind.execute(
            sa.text('UPDATE product_bundles SET modules = :modules WHERE id = :bid'),
            {'modules': json.dumps(modules), 'bid': bundle_id},
        )


def downgrade() -> None:
    bind = op.get_bind()
    result = bind.execute(
        sa.text("SELECT id, modules FROM product_bundles WHERE slug = 'private_doctor_clinic'")
    )
    row = result.fetchone()
    if row is None:
        return
    bundle_id, modules_raw = row[0], row[1]
    try:
        modules = (
            json.loads(modules_raw) if isinstance(modules_raw, str) else list(modules_raw or [])
        )
    except Exception:
        return
    if 'billing' in modules:
        modules = [m for m in modules if m != 'billing']
        bind.execute(
            sa.text('UPDATE product_bundles SET modules = :modules WHERE id = :bid'),
            {'modules': json.dumps(modules), 'bid': bundle_id},
        )
