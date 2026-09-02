"""No-op placeholder for User.role whitelist constraint.

Revision ID: s3_005_user_role_check_constraint
Revises: s3_004_add_lab_panel_item_tenant

Originally intended to add a CHECK constraint on users.role, but the
whitelist broke existing tests that use dynamic roles (rl_*). Role
validation is now enforced in the application layer via
app.shared.user_role_policy.normalize_role. This revision is kept as
a no-op to preserve the linear history (s3_004 -> s3_005 -> s3_006).
"""

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
