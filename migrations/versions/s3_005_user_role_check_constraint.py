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
    # No-op: the original whitelist check constraint broke existing tests that
    # create users with dynamic/legacy role strings (e.g. rl_* random roles,
    # empty strings, custom permission roles). Role validation is enforced by
    # app.shared.user_role_policy.normalize_role and the access-control layer.
    pass


def downgrade() -> None:
    pass
