"""p7_003_telemedicine_consultations — Consultation table for M1 rooms.

Revision ID: p7_003_telemedicine_consultations
Revises: p7_002_shift_handover
Create Date: 2026-08-25
"""

import sqlalchemy as sa
from alembic import op

revision = 'p7_003_telemedicine_consultations'
down_revision = 'p7_002_shift_handover'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'consultations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'tenant_id',
            sa.Integer(),
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'visit_id', sa.Integer(), sa.ForeignKey('visits.id', ondelete='CASCADE'), nullable=False
        ),
        sa.Column(
            'doctor_id',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column(
            'patient_id',
            sa.Integer(),
            sa.ForeignKey('patients.id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column('status', sa.String(20), server_default='SCHEDULED', nullable=False),
        sa.Column('scheduled_at', sa.DateTime(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column(
            'created_by_id',
            sa.Integer(),
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('SCHEDULED','LIVE','COMPLETED','CANCELLED','NO_SHOW')",
            name='chk_consultation_status',
        ),
    )
    op.create_index('idx_consultations_tenant_id', 'consultations', ['tenant_id'])
    op.create_index('ix_consultations_visit_id', 'consultations', ['visit_id'])
    op.create_index('ix_consultations_doctor_id', 'consultations', ['doctor_id'])
    op.create_index('ix_consultations_patient_id', 'consultations', ['patient_id'])
    op.create_index('idx_consult_visit_status', 'consultations', ['visit_id', 'status'])


def downgrade():
    op.drop_index('idx_consult_visit_status', table_name='consultations')
    op.drop_index('ix_consultations_patient_id', table_name='consultations')
    op.drop_index('ix_consultations_doctor_id', table_name='consultations')
    op.drop_index('ix_consultations_visit_id', table_name='consultations')
    op.drop_index('idx_consultations_tenant_id', table_name='consultations')
    op.drop_table('consultations')
