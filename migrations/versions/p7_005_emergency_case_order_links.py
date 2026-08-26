"""p7_005: link emergency_cases to standalone lab/radiology requests.

Adds two nullable FK columns so EmergencyCase can reference LabRequest /
RadiologyRequest created with visit_id=NULL (walk-in safe per p7_001),
replacing the previous non-persisted dict attributes on the model.

Revision: p7_005_emergency_case_order_links
Revises: p7_004_rls_handover_consult
"""

import sqlalchemy as sa
from alembic import op

revision = 'p7_005_emergency_case_order_links'
down_revision = 'p7_004_rls_handover_consult'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'emergency_cases',
        sa.Column('lab_request_id', sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        'fk_emergency_cases_lab_request_id_lab_requests',
        'emergency_cases',
        'lab_requests',
        ['lab_request_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index(
        'ix_emergency_cases_lab_request_id',
        'emergency_cases',
        ['lab_request_id'],
    )
    op.add_column(
        'emergency_cases',
        sa.Column('radiology_request_id', sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        'fk_emergency_cases_radiology_request_id_radiology_requests',
        'emergency_cases',
        'radiology_requests',
        ['radiology_request_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index(
        'ix_emergency_cases_radiology_request_id',
        'emergency_cases',
        ['radiology_request_id'],
    )


def downgrade():
    op.drop_index('ix_emergency_cases_radiology_request_id', table_name='emergency_cases')
    op.drop_constraint(
        'fk_emergency_cases_radiology_request_id_radiology_requests',
        'emergency_cases',
        type_='foreignkey',
    )
    op.drop_column('emergency_cases', 'radiology_request_id')
    op.drop_index('ix_emergency_cases_lab_request_id', table_name='emergency_cases')
    op.drop_constraint(
        'fk_emergency_cases_lab_request_id_lab_requests',
        'emergency_cases',
        type_='foreignkey',
    )
    op.drop_column('emergency_cases', 'lab_request_id')
