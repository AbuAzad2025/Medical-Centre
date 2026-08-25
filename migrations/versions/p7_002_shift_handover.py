"""p7_002_shift_handover — ShiftHandover table for operational shift lifecycle.

Revision ID: p7_002_shift_handover
Revises: p7_001_walk_in_nullable_visit
Create Date: 2026-08-25
"""

import sqlalchemy as sa
from alembic import op

revision = 'p7_002_shift_handover'
down_revision = 'p7_001_walk_in_nullable_visit'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'shift_handovers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'tenant_id',
            sa.Integer(),
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'opened_by_id',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column(
            'closed_by_id',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column(
            'to_user_id',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('role', sa.String(30), nullable=False),
        sa.Column('status', sa.String(20), server_default='OPEN', nullable=False),
        sa.Column('opened_at', sa.DateTime(), nullable=False),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('cash_summary', sa.JSON(), nullable=True),
        sa.Column('pending_items', sa.JSON(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('close_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('OPEN','CLOSED','ACKNOWLEDGED')", name='chk_handover_status'
        ),
    )
    op.create_index('idx_shift_handovers_tenant_id', 'shift_handovers', ['tenant_id'])
    op.create_index('idx_handover_tenant_status', 'shift_handovers', ['tenant_id', 'status'])
    op.create_index('idx_handover_role_opened', 'shift_handovers', ['role', 'opened_at'])


def downgrade():
    op.drop_index('idx_handover_role_opened', table_name='shift_handovers')
    op.drop_index('idx_handover_tenant_status', table_name='shift_handovers')
    op.drop_index('idx_shift_handovers_tenant_id', table_name='shift_handovers')
    op.drop_table('shift_handovers')
