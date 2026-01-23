"""add_follow_up_requests

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-01-21 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'follow_up_requests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('patient_id', sa.Integer(), sa.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False),
        sa.Column('doctor_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('source_visit_id', sa.Integer(), sa.ForeignKey('visits.id', ondelete='SET NULL'), nullable=True),
        sa.Column('appointment_id', sa.Integer(), sa.ForeignKey('appointments.id', ondelete='SET NULL'), nullable=True),
        sa.Column('suggested_date', sa.Date(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='PENDING'),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('PENDING','SCHEDULED','DONE','CANCELLED')", name='chk_follow_up_requests_status')
    )

    op.create_index('ix_follow_up_requests_patient_id', 'follow_up_requests', ['patient_id'], unique=False)
    op.create_index('ix_follow_up_requests_doctor_id', 'follow_up_requests', ['doctor_id'], unique=False)
    op.create_index('ix_follow_up_requests_source_visit_id', 'follow_up_requests', ['source_visit_id'], unique=False)
    op.create_index('ix_follow_up_requests_appointment_id', 'follow_up_requests', ['appointment_id'], unique=False)
    op.create_index('ix_follow_up_requests_suggested_date', 'follow_up_requests', ['suggested_date'], unique=False)
    op.create_index('ix_follow_up_requests_status', 'follow_up_requests', ['status'], unique=False)
    op.create_index('ix_follow_up_requests_created_by', 'follow_up_requests', ['created_by'], unique=False)
    op.create_index('ix_follow_up_requests_created_at', 'follow_up_requests', ['created_at'], unique=False)
    op.create_index('idx_follow_up_requests_patient_status_date', 'follow_up_requests', ['patient_id', 'status', 'suggested_date'], unique=False)
    op.create_index('idx_follow_up_requests_doctor_status_date', 'follow_up_requests', ['doctor_id', 'status', 'suggested_date'], unique=False)


def downgrade():
    op.drop_index('idx_follow_up_requests_doctor_status_date', table_name='follow_up_requests')
    op.drop_index('idx_follow_up_requests_patient_status_date', table_name='follow_up_requests')
    op.drop_index('ix_follow_up_requests_created_at', table_name='follow_up_requests')
    op.drop_index('ix_follow_up_requests_created_by', table_name='follow_up_requests')
    op.drop_index('ix_follow_up_requests_status', table_name='follow_up_requests')
    op.drop_index('ix_follow_up_requests_suggested_date', table_name='follow_up_requests')
    op.drop_index('ix_follow_up_requests_appointment_id', table_name='follow_up_requests')
    op.drop_index('ix_follow_up_requests_source_visit_id', table_name='follow_up_requests')
    op.drop_index('ix_follow_up_requests_doctor_id', table_name='follow_up_requests')
    op.drop_index('ix_follow_up_requests_patient_id', table_name='follow_up_requests')
    op.drop_table('follow_up_requests')

