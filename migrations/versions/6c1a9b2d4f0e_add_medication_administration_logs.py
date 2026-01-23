"""add_medication_administration_logs

Revision ID: 6c1a9b2d4f0e
Revises: 3b7c0a1d9f2e
Create Date: 2026-01-19 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '6c1a9b2d4f0e'
down_revision = '3b7c0a1d9f2e'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'medication_administration_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=False),
        sa.Column('visit_id', sa.Integer(), nullable=False),
        sa.Column('prescription_id', sa.Integer(), nullable=True),
        sa.Column('prescription_item_id', sa.Integer(), nullable=True),
        sa.Column('medication_id', sa.Integer(), nullable=True),
        sa.Column('nurse_id', sa.Integer(), nullable=True),
        sa.Column('administered_at', sa.DateTime(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['medication_id'], ['medications.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['nurse_id'], ['nurses.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['prescription_id'], ['prescriptions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['prescription_item_id'], ['prescription_items.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['visit_id'], ['visits.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('medication_administration_logs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_medication_administration_logs_administered_at'), ['administered_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_medication_administration_logs_medication_id'), ['medication_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_medication_administration_logs_nurse_id'), ['nurse_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_medication_administration_logs_patient_id'), ['patient_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_medication_administration_logs_prescription_id'), ['prescription_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_medication_administration_logs_prescription_item_id'), ['prescription_item_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_medication_administration_logs_visit_id'), ['visit_id'], unique=False)


def downgrade():
    with op.batch_alter_table('medication_administration_logs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_medication_administration_logs_visit_id'))
        batch_op.drop_index(batch_op.f('ix_medication_administration_logs_prescription_item_id'))
        batch_op.drop_index(batch_op.f('ix_medication_administration_logs_prescription_id'))
        batch_op.drop_index(batch_op.f('ix_medication_administration_logs_patient_id'))
        batch_op.drop_index(batch_op.f('ix_medication_administration_logs_nurse_id'))
        batch_op.drop_index(batch_op.f('ix_medication_administration_logs_medication_id'))
        batch_op.drop_index(batch_op.f('ix_medication_administration_logs_administered_at'))
    op.drop_table('medication_administration_logs')

