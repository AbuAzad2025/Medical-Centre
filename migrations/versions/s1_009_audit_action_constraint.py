"""Add APPROVE/REJECT to audit_trails chk_action (Ticket 3 corrective)

Revision ID: s1_009_audit_action_constraint
Revises: s1_008_custom_service_lifecycle
Create Date: 2026-07-02

"""
from alembic import op
import sqlalchemy as sa

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from migration_utils import check_constraint_exists


revision = 's1_009_audit_action_constraint'
down_revision = 's1_008_custom_service_lifecycle'
branch_labels = None
depends_on = None


def upgrade():
    if check_constraint_exists('audit_trails', 'chk_action'):
        op.drop_constraint('chk_action', 'audit_trails', type_='check')
    op.create_check_constraint(
        'chk_action',
        'audit_trails',
        sa.sql.text("action IN ('create', 'update', 'delete', 'view', 'login', 'logout', 'export', 'import', 'backup', 'restore', 'security', 'login_failed', 'login_blocked', 'force_logout', 'permission_denied', 'unauthorized_access', 'APPROVE', 'REJECT')")
    )


def downgrade():
    if check_constraint_exists('audit_trails', 'chk_action'):
        op.drop_constraint('chk_action', 'audit_trails', type_='check')
    op.create_check_constraint(
        'chk_action',
        'audit_trails',
        sa.sql.text("action IN ('create', 'update', 'delete', 'view', 'login', 'logout', 'export', 'import', 'backup', 'restore', 'security', 'login_failed', 'login_blocked', 'force_logout', 'permission_denied', 'unauthorized_access')")
    )
