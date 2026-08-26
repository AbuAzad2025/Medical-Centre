"""p7_006: real treatment columns for emergency_cases.

routes/emergency/treatment.py and cases.py wrote non-persisted
attributes (treatment_given, medications, procedures, treated_by/at,
completed_by, treatment_started_at) that silently vanished on commit.
This migration adds the real columns; the routes now write these
snake_case names.

Revision: p7_006_emergency_treatment_fields
Revises: p7_005_emergency_case_order_links
"""

import sqlalchemy as sa
from alembic import op

revision = 'p7_006_emergency_treatment_fields'
down_revision = 'p7_005_emergency_case_order_links'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('emergency_cases', sa.Column('treatment_given', sa.Text(), nullable=True))
    op.add_column('emergency_cases', sa.Column('medications_text', sa.Text(), nullable=True))
    op.add_column('emergency_cases', sa.Column('procedures_text', sa.Text(), nullable=True))
    op.add_column('emergency_cases', sa.Column('treated_by_id', sa.Integer(), nullable=True))
    op.add_column(
        'emergency_cases', sa.Column('treatment_started_at', sa.DateTime(), nullable=True)
    )
    op.add_column(
        'emergency_cases', sa.Column('treatment_completed_at', sa.DateTime(), nullable=True)
    )
    op.add_column('emergency_cases', sa.Column('completed_by_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_emergency_cases_treated_by_id_users',
        'emergency_cases',
        'users',
        ['treated_by_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_emergency_cases_completed_by_id_users',
        'emergency_cases',
        'users',
        ['completed_by_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index('ix_emergency_cases_treated_by_id', 'emergency_cases', ['treated_by_id'])
    op.create_index('ix_emergency_cases_completed_by_id', 'emergency_cases', ['completed_by_id'])


def downgrade():
    op.drop_index('ix_emergency_cases_completed_by_id', table_name='emergency_cases')
    op.drop_index('ix_emergency_cases_treated_by_id', table_name='emergency_cases')
    op.drop_constraint(
        'fk_emergency_cases_completed_by_id_users', 'emergency_cases', type_='foreignkey'
    )
    op.drop_constraint(
        'fk_emergency_cases_treated_by_id_users', 'emergency_cases', type_='foreignkey'
    )
    op.drop_column('emergency_cases', 'completed_by_id')
    op.drop_column('emergency_cases', 'treatment_completed_at')
    op.drop_column('emergency_cases', 'treatment_started_at')
    op.drop_column('emergency_cases', 'treated_by_id')
    op.drop_column('emergency_cases', 'procedures_text')
    op.drop_column('emergency_cases', 'medications_text')
    op.drop_column('emergency_cases', 'treatment_given')
