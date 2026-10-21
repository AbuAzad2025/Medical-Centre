"""Permit the credential and session audit actions on audit_trails.

The application writes three audit rows the schema forbids:

  * action='PASSWORD_CHANGE'   - a credential change (routes/auth_routes.py)
  * action='TERMINATE_OTHER_SESSIONS' - a session revocation
  * entity_type='user_session'  - the entity those rows describe

The ORM declares them, so the model and the constraint disagree. Every write
of those rows is refused by the database with a CheckViolation, and the write is
swallowed by the handler around it - so a password change left no audit row at
all, and nobody could tell from the record that the credential had been
changed. The comment in the route says "a credential change is the row an
investigator looks for"; that row was never written.

The test harness patched the constraint at test time, which is why the tests
passed against a schema production would have rejected. This migration brings
the database in line with the model, and the harness patch is no longer
carrying the difference on its own.

Revision: s3_019_audit_credential_actions
Revises: s3_018_drug_interactions_tenant
Create Date: 2026-10-21
"""

import os
import sys

import sqlalchemy as sa
from alembic import op

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from migration_utils import check_constraint_exists  # noqa: E402

revision = 's3_019_audit_credential_actions'
down_revision = 's3_018_drug_interactions_tenant'
branch_labels = None
depends_on = None

ACTION_VALUES = (
    "'create', 'update', 'delete', 'view', 'login', 'logout', "
    "'export', 'import', 'backup', 'restore', 'security', 'login_failed', "
    "'login_blocked', 'force_logout', 'permission_denied', 'unauthorized_access', "
    "'APPROVE', 'REJECT', 'IMPERSONATE', 'PASSWORD_CHANGE', 'TERMINATE_OTHER_SESSIONS'"
)

ENTITY_TYPE_VALUES = (
    "'system', 'user', 'patient', 'visit', 'appointment', 'payment', 'invoice', "
    "'lab_test', 'radiology_test', 'notification', 'role', 'department', 'service', "
    "'user_session'"
)


def upgrade() -> None:
    if check_constraint_exists('audit_trails', 'chk_action'):
        op.drop_constraint('chk_action', 'audit_trails', type_='check')
    op.create_check_constraint(
        'chk_action',
        'audit_trails',
        sa.text(f'action IN ({ACTION_VALUES})'),
    )

    if check_constraint_exists('audit_trails', 'chk_entity_type'):
        op.drop_constraint('chk_entity_type', 'audit_trails', type_='check')
    op.create_check_constraint(
        'chk_entity_type',
        'audit_trails',
        sa.text(f'entity_type IN ({ENTITY_TYPE_VALUES})'),
    )


def downgrade() -> None:
    if check_constraint_exists('audit_trails', 'chk_action'):
        op.drop_constraint('chk_action', 'audit_trails', type_='check')
    op.create_check_constraint(
        'chk_action',
        'audit_trails',
        sa.text(
            "action IN ('create', 'update', 'delete', 'view', 'login', 'logout', "
            "'export', 'import', 'backup', 'restore', 'security', 'login_failed', "
            "'login_blocked', 'force_logout', 'permission_denied', 'unauthorized_access', "
            "'APPROVE', 'REJECT', 'IMPERSONATE')"
        ),
    )

    if check_constraint_exists('audit_trails', 'chk_entity_type'):
        op.drop_constraint('chk_entity_type', 'audit_trails', type_='check')
    op.create_check_constraint(
        'chk_entity_type',
        'audit_trails',
        sa.text(
            "entity_type IN ('system', 'user', 'patient', 'visit', 'appointment', "
            "'payment', 'invoice', 'lab_test', 'radiology_test', 'notification', "
            "'role', 'department', 'service')"
        ),
    )
