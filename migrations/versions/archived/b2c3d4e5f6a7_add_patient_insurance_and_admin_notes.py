"""add_patient_insurance_and_admin_notes

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-01-21 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('patients', schema=None) as batch_op:
        batch_op.add_column(sa.Column('admin_notes', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('insurance_company_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('insurance_member_number', sa.String(length=60), nullable=True))
        batch_op.create_index(batch_op.f('ix_patients_insurance_company_id'), ['insurance_company_id'], unique=False)
        batch_op.create_foreign_key('fk_patients_insurance_company_id', 'insurance_companies', ['insurance_company_id'], ['id'], ondelete='SET NULL')


def downgrade():
    with op.batch_alter_table('patients', schema=None) as batch_op:
        batch_op.drop_constraint('fk_patients_insurance_company_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_patients_insurance_company_id'))
        batch_op.drop_column('insurance_member_number')
        batch_op.drop_column('insurance_company_id')
        batch_op.drop_column('admin_notes')

