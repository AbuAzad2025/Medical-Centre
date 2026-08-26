"""p7_007_make_prescription_id_nullable_in_emar_administrations

Make prescription_id nullable in emar_administrations table.

Revision ID: p7_007_make_prescription_id_nullable
Revises: p7_006_emergency_treatment_fields
Create Date: 2026-08-26
"""

import sqlalchemy as sa
from alembic import op

revision = 'p7_007_make_prescription_id_nullable'
down_revision = 'p7_006_emergency_treatment_fields'
branch_labels = None
depends_on = None


def upgrade():
    # Make prescription_id nullable in emar_administrations
    with op.batch_alter_table('emar_administrations', schema=None) as batch_op:
        batch_op.alter_column('prescription_id',
                              existing_type=sa.INTEGER(),
                              nullable=True,
                              existing_nullable=False)


def downgrade():
    with op.batch_alter_table('emar_administrations', schema=None) as batch_op:
        batch_op.alter_column('prescription_id',
                              existing_type=sa.INTEGER(),
                              nullable=False,
                              existing_nullable=True)