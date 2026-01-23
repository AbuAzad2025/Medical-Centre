"""auth_security_audit_constraints_and_login_attempts

Revision ID: a1b2c3d4e5f6
Revises: 9f0e1d2c3b4a
Create Date: 2026-01-21 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = '9f0e1d2c3b4a'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('audit_trails', schema=None) as batch_op:
        batch_op.drop_constraint('chk_action', type_='check')
        batch_op.drop_constraint('chk_entity_type', type_='check')
        batch_op.create_check_constraint(
            'chk_entity_type',
            "entity_type IN ('system', 'user', 'patient', 'visit', 'appointment', 'payment', 'invoice', 'lab_test', 'radiology_test', 'notification', 'role', 'department')"
        )
        batch_op.create_check_constraint(
            'chk_action',
            "action IN ('create', 'update', 'delete', 'view', 'login', 'logout', 'export', 'import', 'backup', 'restore', 'security', 'login_failed', 'login_blocked', 'force_logout', 'permission_denied', 'unauthorized_access')"
        )

    op.create_table(
        'login_attempts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=80), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('user_ip', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('login_attempts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_login_attempts_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_login_attempts_success'), ['success'], unique=False)
        batch_op.create_index(batch_op.f('ix_login_attempts_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_login_attempts_user_ip'), ['user_ip'], unique=False)
        batch_op.create_index(batch_op.f('ix_login_attempts_username'), ['username'], unique=False)


def downgrade():
    with op.batch_alter_table('login_attempts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_login_attempts_username'))
        batch_op.drop_index(batch_op.f('ix_login_attempts_user_ip'))
        batch_op.drop_index(batch_op.f('ix_login_attempts_user_id'))
        batch_op.drop_index(batch_op.f('ix_login_attempts_success'))
        batch_op.drop_index(batch_op.f('ix_login_attempts_created_at'))
    op.drop_table('login_attempts')

    with op.batch_alter_table('audit_trails', schema=None) as batch_op:
        batch_op.drop_constraint('chk_action', type_='check')
        batch_op.drop_constraint('chk_entity_type', type_='check')
        batch_op.create_check_constraint(
            'chk_entity_type',
            "entity_type IN ('user', 'patient', 'visit', 'appointment', 'payment', 'invoice', 'lab_test', 'radiology_test', 'notification', 'role', 'department')"
        )
        batch_op.create_check_constraint(
            'chk_action',
            "action IN ('create', 'update', 'delete', 'view', 'login', 'logout', 'export', 'import', 'backup', 'restore')"
        )

