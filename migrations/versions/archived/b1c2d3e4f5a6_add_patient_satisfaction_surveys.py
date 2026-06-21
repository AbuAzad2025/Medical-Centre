"""add_patient_satisfaction_surveys

Revision ID: b1c2d3e4f5a6
Revises: a0b1c2d3e4f5
Create Date: 2026-01-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b1c2d3e4f5a6'
down_revision = 'a0b1c2d3e4f5'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'patient_satisfaction_surveys',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('visit_id', sa.Integer(), sa.ForeignKey('visits.id', ondelete='CASCADE'), nullable=False),
        sa.Column('patient_id', sa.Integer(), sa.ForeignKey('patients.id', ondelete='SET NULL'), nullable=True),
        sa.Column('token', sa.String(length=120), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=True),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'))
    )
    op.create_index('idx_survey_token', 'patient_satisfaction_surveys', ['token'], unique=True)
    op.create_index('idx_survey_visit', 'patient_satisfaction_surveys', ['visit_id'], unique=False)
    op.create_index('idx_survey_patient', 'patient_satisfaction_surveys', ['patient_id'], unique=False)
    op.create_index('idx_survey_created', 'patient_satisfaction_surveys', ['created_at'], unique=False)


def downgrade():
    op.drop_index('idx_survey_created', table_name='patient_satisfaction_surveys')
    op.drop_index('idx_survey_patient', table_name='patient_satisfaction_surveys')
    op.drop_index('idx_survey_visit', table_name='patient_satisfaction_surveys')
    op.drop_index('idx_survey_token', table_name='patient_satisfaction_surveys')
    op.drop_table('patient_satisfaction_surveys')
