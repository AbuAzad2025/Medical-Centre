"""Create phi_audit_logs table for immutable PHI access audit trail

Revision ID: s2_003_phi_audit_log
Revises: s2_002_ghost_impersonate_action
Create Date: 2026-07-28

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON, VARCHAR

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from migration_utils import table_exists


revision = 's2_003_phi_audit_log'
down_revision = 's2_002_ghost_impersonate_action'
branch_labels = None
depends_on = None


def upgrade():
    if table_exists('phi_audit_logs'):
        return

    op.create_table(
        'phi_audit_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('actor_id', sa.Integer(), nullable=True, index=True),
        sa.Column('ip_address', VARCHAR(45), nullable=True),
        sa.Column('request_id', VARCHAR(36), nullable=True, index=True),
        sa.Column('target_model', VARCHAR(64), nullable=False, index=True),
        sa.Column('target_id', sa.Integer(), nullable=False, index=True),
        sa.Column('action', VARCHAR(10), nullable=False, index=True),
        sa.Column('changes', JSON(), nullable=True),
        sa.Column('tenant_id', sa.Integer(), nullable=True, index=True),
        sa.Column('created_at', sa.DateTime(), nullable=False,
                  server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id'],
                                ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "action IN ('CREATE', 'UPDATE', 'DELETE')",
            name='ck_phi_audit_action',
        ),
    )

    op.create_index('idx_phi_audit_target', 'phi_audit_logs',
                    ['target_model', 'target_id'])
    op.create_index('idx_phi_audit_created', 'phi_audit_logs',
                    ['created_at'])

    # Revoke UPDATE/DELETE at the database level for defense in depth.
    # This requires the application DB user to be distinct from the migration user.
    # Wrapped in try/except so the migration works in dev/test where the role
    # may not exist or may be the same as the migration user.
    app_user = _get_app_user()
    if app_user:
        for stmt in [
            f"REVOKE UPDATE ON phi_audit_logs FROM \"{app_user}\"",
            f"REVOKE DELETE ON phi_audit_logs FROM \"{app_user}\"",
        ]:
            try:
                op.execute(stmt)
            except Exception:
                pass


def downgrade():
    if not table_exists('phi_audit_logs'):
        return

    # Restore privileges (best-effort)
    app_user = _get_app_user()
    if app_user:
        for stmt in [
            f"GRANT UPDATE ON phi_audit_logs TO \"{app_user}\"",
            f"GRANT DELETE ON phi_audit_logs TO \"{app_user}\"",
        ]:
            try:
                op.execute(stmt)
            except Exception:
                pass

    op.drop_table('phi_audit_logs')


def _get_app_user():
    try:
        url = op.get_bind().engine.url
        if url.username and url.username != 'postgres':
            return url.username
    except Exception:
        pass
    return None
