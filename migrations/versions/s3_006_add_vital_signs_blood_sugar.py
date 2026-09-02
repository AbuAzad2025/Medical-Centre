"""Add blood_sugar column to vital_signs.

Revision ID: s3_006_add_vital_signs_blood_sugar
Revises: s3_005_user_role_check_constraint

The application model (models.nurse.VitalSigns) already expects
blood_sugar, but the baseline migration did not include it. Tests
previously added it dynamically; this migration makes it permanent.
"""

import sqlalchemy as sa
from alembic import op

revision = 's3_006_add_vital_signs_blood_sugar'
down_revision = 's3_005_user_role_check_constraint'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'vital_signs',
        sa.Column('blood_sugar', sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('vital_signs', 'blood_sugar')
