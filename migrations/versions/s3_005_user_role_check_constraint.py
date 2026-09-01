"""Add CheckConstraint on User.role to enforce role whitelist.

Revision ID: s3_005_user_role_check_constraint
Revises: s3_004_add_lab_panel_item_tenant

Adds a database-level check constraint on users.role to validate
against a unified whitelist that includes canonical roles and legacy
aliases (receptionist, lab_tech, platform_owner) for backward
compatibility.
"""

from alembic import op
from sqlalchemy import text

revision = 's3_005_user_role_check_constraint'
down_revision = 's3_004_add_lab_panel_item_tenant'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute(
            text(
                """
                ALTER TABLE users
                ADD CONSTRAINT chk_user_role
                CHECK (role IN (
                    'admin','super_admin','manager','doctor','nurse',
                    'reception','accountant','emergency','lab','radiology',
                    'pharmacist','technician','owner','patient','user',
                    'receptionist','lab_tech','platform_owner'
                ))
                """
            )
        )
    else:
        # SQLite does not enforce CHECK constraints on ALTER TABLE in older versions,
        # but we include the DDL for completeness.
        op.execute(
            text(
                """
                ALTER TABLE users
                ADD CONSTRAINT chk_user_role
                CHECK (role IN (
                    'admin','super_admin','manager','doctor','nurse',
                    'reception','accountant','emergency','lab','radiology',
                    'pharmacist','technician','owner','patient','user',
                    'receptionist','lab_tech','platform_owner'
                ))
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute(text("ALTER TABLE users DROP CONSTRAINT IF EXISTS chk_user_role"))
    else:
        op.execute(text("ALTER TABLE users DROP CONSTRAINT IF EXISTS chk_user_role"))
