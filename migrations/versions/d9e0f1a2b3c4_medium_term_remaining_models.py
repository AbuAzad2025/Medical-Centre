"""medium_term_remaining_models

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
Create Date: 2026-01-21 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = 'd9e0f1a2b3c4'
down_revision = 'c8d9e0f1a2b3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'patient_accounts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('patient_id'),
        sa.UniqueConstraint('user_id'),
    )
    with op.batch_alter_table('patient_accounts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_patient_accounts_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_patient_accounts_patient_id'), ['patient_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_patient_accounts_user_id'), ['user_id'], unique=False)

    op.create_table(
        'user_department_access',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('department_id', sa.Integer(), nullable=False),
        sa.Column('can_access', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['department_id'], ['departments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'department_id', name='uq_user_department_access'),
    )
    with op.batch_alter_table('user_department_access', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_user_department_access_can_access'), ['can_access'], unique=False)
        batch_op.create_index(batch_op.f('ix_user_department_access_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_user_department_access_department_id'), ['department_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_user_department_access_user_id'), ['user_id'], unique=False)

    op.create_table(
        'visit_transfer_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('visit_id', sa.Integer(), nullable=False),
        sa.Column('from_department_id', sa.Integer(), nullable=True),
        sa.Column('to_department_id', sa.Integer(), nullable=True),
        sa.Column('from_doctor_id', sa.Integer(), nullable=True),
        sa.Column('to_doctor_id', sa.Integer(), nullable=True),
        sa.Column('transferred_by', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(length=30), nullable=False, server_default='reception'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['from_department_id'], ['departments.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['from_doctor_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['to_department_id'], ['departments.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['to_doctor_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['transferred_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['visit_id'], ['visits.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('visit_transfer_logs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_visit_transfer_logs_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_visit_transfer_logs_from_department_id'), ['from_department_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_visit_transfer_logs_from_doctor_id'), ['from_doctor_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_visit_transfer_logs_source'), ['source'], unique=False)
        batch_op.create_index(batch_op.f('ix_visit_transfer_logs_to_department_id'), ['to_department_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_visit_transfer_logs_to_doctor_id'), ['to_doctor_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_visit_transfer_logs_transferred_by'), ['transferred_by'], unique=False)
        batch_op.create_index(batch_op.f('ix_visit_transfer_logs_visit_id'), ['visit_id'], unique=False)

    op.create_table(
        'emergency_status_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('emergency_id', sa.Integer(), nullable=False),
        sa.Column('from_status', sa.String(length=50), nullable=True),
        sa.Column('to_status', sa.String(length=50), nullable=False),
        sa.Column('changed_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['changed_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['emergency_id'], ['emergency_cases.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('emergency_status_history', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_emergency_status_history_changed_by'), ['changed_by'], unique=False)
        batch_op.create_index(batch_op.f('ix_emergency_status_history_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_emergency_status_history_emergency_id'), ['emergency_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_emergency_status_history_from_status'), ['from_status'], unique=False)
        batch_op.create_index(batch_op.f('ix_emergency_status_history_to_status'), ['to_status'], unique=False)

    with op.batch_alter_table('radiology_results', schema=None) as batch_op:
        batch_op.add_column(sa.Column('reviewed_by', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('reviewed_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('revised_after_review', sa.Boolean(), nullable=False, server_default=sa.text('false')))
        batch_op.create_index(batch_op.f('ix_radiology_results_reviewed_by'), ['reviewed_by'], unique=False)
        batch_op.create_index(batch_op.f('ix_radiology_results_reviewed_at'), ['reviewed_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_radiology_results_revised_after_review'), ['revised_after_review'], unique=False)
        batch_op.create_foreign_key('fk_radiology_results_reviewed_by_users', 'users', ['reviewed_by'], ['id'], ondelete='SET NULL')


def downgrade():
    with op.batch_alter_table('radiology_results', schema=None) as batch_op:
        batch_op.drop_constraint('fk_radiology_results_reviewed_by_users', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_radiology_results_revised_after_review'))
        batch_op.drop_index(batch_op.f('ix_radiology_results_reviewed_at'))
        batch_op.drop_index(batch_op.f('ix_radiology_results_reviewed_by'))
        batch_op.drop_column('revised_after_review')
        batch_op.drop_column('reviewed_at')
        batch_op.drop_column('reviewed_by')

    with op.batch_alter_table('emergency_status_history', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_emergency_status_history_to_status'))
        batch_op.drop_index(batch_op.f('ix_emergency_status_history_from_status'))
        batch_op.drop_index(batch_op.f('ix_emergency_status_history_emergency_id'))
        batch_op.drop_index(batch_op.f('ix_emergency_status_history_created_at'))
        batch_op.drop_index(batch_op.f('ix_emergency_status_history_changed_by'))
    op.drop_table('emergency_status_history')

    with op.batch_alter_table('visit_transfer_logs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_visit_transfer_logs_visit_id'))
        batch_op.drop_index(batch_op.f('ix_visit_transfer_logs_transferred_by'))
        batch_op.drop_index(batch_op.f('ix_visit_transfer_logs_to_doctor_id'))
        batch_op.drop_index(batch_op.f('ix_visit_transfer_logs_to_department_id'))
        batch_op.drop_index(batch_op.f('ix_visit_transfer_logs_source'))
        batch_op.drop_index(batch_op.f('ix_visit_transfer_logs_from_doctor_id'))
        batch_op.drop_index(batch_op.f('ix_visit_transfer_logs_from_department_id'))
        batch_op.drop_index(batch_op.f('ix_visit_transfer_logs_created_at'))
    op.drop_table('visit_transfer_logs')

    with op.batch_alter_table('user_department_access', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_department_access_user_id'))
        batch_op.drop_index(batch_op.f('ix_user_department_access_department_id'))
        batch_op.drop_index(batch_op.f('ix_user_department_access_created_at'))
        batch_op.drop_index(batch_op.f('ix_user_department_access_can_access'))
    op.drop_table('user_department_access')

    with op.batch_alter_table('patient_accounts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_patient_accounts_user_id'))
        batch_op.drop_index(batch_op.f('ix_patient_accounts_patient_id'))
        batch_op.drop_index(batch_op.f('ix_patient_accounts_created_at'))
    op.drop_table('patient_accounts')
