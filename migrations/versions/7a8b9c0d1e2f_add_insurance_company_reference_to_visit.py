"""add_insurance_company_reference_to_visit

Revision ID: 7a8b9c0d1e2f
Revises: d9e0f1a2b3c4
Create Date: 2026-01-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7a8b9c0d1e2f'
down_revision = 'd9e0f1a2b3c4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('visits', schema=None) as batch_op:
        batch_op.add_column(sa.Column('insurance_company_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_visits_insurance_company_id'), ['insurance_company_id'], unique=False)
        batch_op.create_index('idx_visit_payment_method', ['payment_method'], unique=False)
        batch_op.create_foreign_key(
            'fk_visits_insurance_company_id',
            'insurance_companies',
            ['insurance_company_id'],
            ['id'],
            ondelete='SET NULL'
        )
    with op.batch_alter_table('insurance_claims', schema=None) as batch_op:
        batch_op.create_index('idx_insurance_claim_company_status', ['company_id', 'status'], unique=False)
        batch_op.create_index('idx_insurance_claim_status', ['status'], unique=False)
        batch_op.create_index('idx_insurance_claim_created', ['created_at'], unique=False)


def downgrade():
    with op.batch_alter_table('visits', schema=None) as batch_op:
        batch_op.drop_constraint('fk_visits_insurance_company_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_visits_insurance_company_id'))
        batch_op.drop_index('idx_visit_payment_method')
        batch_op.drop_column('insurance_company_id')
    with op.batch_alter_table('insurance_claims', schema=None) as batch_op:
        batch_op.drop_index('idx_insurance_claim_company_status')
        batch_op.drop_index('idx_insurance_claim_status')
        batch_op.drop_index('idx_insurance_claim_created')
