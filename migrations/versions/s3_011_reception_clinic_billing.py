"""Add billing to doctor_clinic_reception for reception billing flow.

Revision ID: s3_011_reception_clinic_billing
Revises: s3_010_private_doctor_billing
"""

import json

import sqlalchemy as sa
from alembic import op

revision = 's3_011_reception_clinic_billing'
down_revision = 's3_010_private_doctor_billing'
branch_labels = None
depends_on = None


def _add_billing(slug: str, order: list[str]) -> None:
    bind = op.get_bind()
    result = bind.execute(
        sa.text('SELECT id, modules FROM product_bundles WHERE slug = :slug'), {'slug': slug}
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
        modules = sorted(modules, key=lambda m: order.index(m) if m in order else 99)
        bind.execute(
            sa.text('UPDATE product_bundles SET modules = :modules WHERE id = :bid'),
            {'modules': json.dumps(modules), 'bid': bundle_id},
        )


def _remove_billing(slug: str) -> None:
    bind = op.get_bind()
    result = bind.execute(
        sa.text('SELECT id, modules FROM product_bundles WHERE slug = :slug'), {'slug': slug}
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


def upgrade() -> None:
    _add_billing('doctor_clinic_reception', ['reception', 'doctor', 'billing', 'appointments'])


def downgrade() -> None:
    _remove_billing('doctor_clinic_reception')
