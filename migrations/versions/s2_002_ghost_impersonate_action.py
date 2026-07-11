"""Permit 'IMPERSONATE' audit action for Ghost Mode (master impersonation)

Revision ID: s2_002_ghost_impersonate_action
Revises: s2_001_tenant_id_not_null
Create Date: 2026-07-11

"""
from alembic import op
import sqlalchemy as sa

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from migration_utils import check_constraint_exists


revision = 's2_002_ghost_impersonate_action'
down_revision = 's2_001_tenant_id_not_null'
branch_labels = None
depends_on = None


def upgrade():
    if check_constraint_exists('audit_trails', 'chk_action'):
        op.drop_constraint('chk_action', 'audit_trails', type_='check')
    op.create_check_constraint(
        'chk_action',
        'audit_trails',
        sa.sql.text(
            "action IN ('create', 'update', 'delete', 'view', 'login', 'logout', "
            "'export', 'import', 'backup', 'restore', 'security', 'login_failed', "
            "'login_blocked', 'force_logout', 'permission_denied', 'unauthorized_access', "
            "'APPROVE', 'REJECT', 'IMPERSONATE')"
        ),
    )


def downgrade():
    if check_constraint_exists('audit_trails', 'chk_action'):
        op.drop_constraint('chk_action', 'audit_trails', type_='check')
    op.create_check_constraint(
        'chk_action',
        'audit_trails',
        sa.sql.text(
            "action IN ('create', 'update', 'delete', 'view', 'login', 'logout', "
            "'export', 'import', 'backup', 'restore', 'security', 'login_failed', "
            "'login_blocked', 'force_logout', 'permission_denied', 'unauthorized_access', "
            "'APPROVE', 'REJECT')"
        ),
    )
