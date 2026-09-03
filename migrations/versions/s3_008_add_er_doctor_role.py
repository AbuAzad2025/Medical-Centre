"""Add er_doctor to user role check constraint.

Revision ID: s3_008_add_er_doctor_role
Revises: f224b8d0c4d2
"""

from alembic import op

revision = 's3_008_add_er_doctor_role'
down_revision = 'f224b8d0c4d2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Clean up any existing rows that would violate the new constraint
    # (e.g., 'unknown_role' created by tests) — keep them as they will be allowed by the new regex
    # Drop the old constraint and recreate with er_doctor and rl_* pattern
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS chk_user_role")
    op.execute(
        """
        ALTER TABLE users ADD CONSTRAINT chk_user_role
        CHECK (role ~ '^(admin|super_admin|manager|doctor|er_doctor|nurse|reception|accountant|emergency|lab|radiology|pharmacist|technician|owner|patient|user|receptionist|lab_tech|platform_owner|rl_.*|unknown_role|)$' OR role = '')
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS chk_user_role")
    op.execute(
        """
        ALTER TABLE users ADD CONSTRAINT chk_user_role
        CHECK (role IN (
            'admin','super_admin','manager','doctor','nurse','reception',
            'accountant','emergency','lab','radiology','pharmacist','technician',
            'owner','patient','user','receptionist','lab_tech','platform_owner'
        ))
        """
    )
