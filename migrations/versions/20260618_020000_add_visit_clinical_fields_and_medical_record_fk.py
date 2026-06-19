"""Add visit clinical fields, medical_record visit_id FK, fix treatment constraint

Revision ID: 20260618_020000
Revises: 20260613_030000
Create Date: 2026-06-18 02:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260618_020000'
down_revision = '20260613_030000'
branch_labels = None
depends_on = None


def upgrade():
    # Add clinical fields to visits table
    op.add_column('visits', sa.Column('chief_complaint', sa.Text(), nullable=True))
    op.add_column('visits', sa.Column('differential_diagnosis', sa.Text(), nullable=True))
    op.add_column('visits', sa.Column('follow_up_notes', sa.Text(), nullable=True))
    op.add_column('visits', sa.Column('vital_signs', sa.Text(), nullable=True))

    # Add visit_id FK and diagnosis column to medical_records
    op.add_column('medical_records', sa.Column('visit_id', sa.Integer(), sa.ForeignKey('visits.id', ondelete='CASCADE'), nullable=True, index=True))
    op.add_column('medical_records', sa.Column('diagnosis', sa.Text(), nullable=True))

    # Fix treatment status check constraint
    op.execute("ALTER TABLE treatments DROP CONSTRAINT IF EXISTS chk_treatment_status")
    op.create_check_constraint(
        "chk_treatment_status",
        "treatments",
        sa.text("status IN ('pending', 'active', 'completed', 'cancelled', 'follow_up')")
    )

    # Add ondelete='SET NULL' to receipt FKs that were missing it
    op.drop_constraint('receipts_debt_approved_by_fkey', 'receipts', type_='foreignkey')
    op.create_foreign_key('receipts_debt_approved_by_fkey', 'receipts', 'users', ['debt_approved_by'], ['id'], ondelete='SET NULL')
    op.drop_constraint('receipts_printed_by_fkey', 'receipts', type_='foreignkey')
    op.create_foreign_key('receipts_printed_by_fkey', 'receipts', 'users', ['printed_by'], ['id'], ondelete='SET NULL')
    op.drop_constraint('receipts_created_by_fkey', 'receipts', type_='foreignkey')
    op.create_foreign_key('receipts_created_by_fkey', 'receipts', 'users', ['created_by'], ['id'], ondelete='SET NULL')


def downgrade():
    # Revert receipt FK ondelete (remove SET NULL)
    op.drop_constraint('receipts_debt_approved_by_fkey', 'receipts', type_='foreignkey')
    op.create_foreign_key('receipts_debt_approved_by_fkey', 'receipts', 'users', ['debt_approved_by'], ['id'])
    op.drop_constraint('receipts_printed_by_fkey', 'receipts', type_='foreignkey')
    op.create_foreign_key('receipts_printed_by_fkey', 'receipts', 'users', ['printed_by'], ['id'])
    op.drop_constraint('receipts_created_by_fkey', 'receipts', type_='foreignkey')
    op.create_foreign_key('receipts_created_by_fkey', 'receipts', 'users', ['created_by'], ['id'])

    # Fix treatment status check constraint (revert)
    op.execute("ALTER TABLE treatments DROP CONSTRAINT IF EXISTS chk_treatment_status")
    op.create_check_constraint(
        "chk_treatment_status",
        "treatments",
        sa.text("status IN ('active', 'completed', 'cancelled', 'suspended')")
    )

    # Remove columns from medical_records
    op.drop_column('medical_records', 'diagnosis')
    op.drop_column('medical_records', 'visit_id')

    # Remove columns from visits
    op.drop_column('visits', 'vital_signs')
    op.drop_column('visits', 'follow_up_notes')
    op.drop_column('visits', 'differential_diagnosis')
    op.drop_column('visits', 'chief_complaint')
