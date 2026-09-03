"""Add pending_financial_settlement flag for hub-and-spoke financial gate.

Revision ID: s3_009_pending_financial_settlement
Revises: s3_008_add_er_doctor_role
"""

from alembic import op
import sqlalchemy as sa

revision = 's3_009_pending_financial_settlement'
down_revision = 's3_008_add_er_doctor_role'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('visits', sa.Column('pending_financial_settlement', sa.Boolean(), nullable=False, server_default='false'))
    op.create_index('idx_visit_pending_settlement', 'visits', ['pending_financial_settlement'])


def downgrade() -> None:
    op.drop_index('idx_visit_pending_settlement', table_name='visits')
    op.drop_column('visits', 'pending_financial_settlement')
