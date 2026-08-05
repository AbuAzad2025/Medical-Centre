"""add disposition to pharmacy_returns

Revision ID: f9278aacbb94
Revises: s2_009_schema_drift_sync
Create Date: 2026-08-05 14:00:27.341908

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f9278aacbb94'
down_revision = 's2_009_schema_drift_sync'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('pharmacy_returns', sa.Column('disposition', sa.String(20), nullable=False, server_default='RESTOCK'))


def downgrade():
    op.drop_column('pharmacy_returns', 'disposition')
