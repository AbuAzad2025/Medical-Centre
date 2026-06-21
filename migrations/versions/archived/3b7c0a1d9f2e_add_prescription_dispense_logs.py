"""add_prescription_dispense_logs

Revision ID: 3b7c0a1d9f2e
Revises: ef5e2c54c0ea
Create Date: 2026-01-19 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3b7c0a1d9f2e'
down_revision = 'ef5e2c54c0ea'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'prescription_dispense_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('prescription_id', sa.Integer(), nullable=False),
        sa.Column('patient_id', sa.Integer(), nullable=True),
        sa.Column('visit_id', sa.Integer(), nullable=True),
        sa.Column('dispensed_by', sa.Integer(), nullable=True),
        sa.Column('dispensed_at', sa.DateTime(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['dispensed_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['prescription_id'], ['prescriptions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['visit_id'], ['visits.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('prescription_dispense_logs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_prescription_dispense_logs_dispensed_at'), ['dispensed_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_prescription_dispense_logs_dispensed_by'), ['dispensed_by'], unique=False)
        batch_op.create_index(batch_op.f('ix_prescription_dispense_logs_patient_id'), ['patient_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_prescription_dispense_logs_prescription_id'), ['prescription_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_prescription_dispense_logs_visit_id'), ['visit_id'], unique=False)


def downgrade():
    with op.batch_alter_table('prescription_dispense_logs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_prescription_dispense_logs_visit_id'))
        batch_op.drop_index(batch_op.f('ix_prescription_dispense_logs_prescription_id'))
        batch_op.drop_index(batch_op.f('ix_prescription_dispense_logs_patient_id'))
        batch_op.drop_index(batch_op.f('ix_prescription_dispense_logs_dispensed_by'))
        batch_op.drop_index(batch_op.f('ix_prescription_dispense_logs_dispensed_at'))
    op.drop_table('prescription_dispense_logs')

