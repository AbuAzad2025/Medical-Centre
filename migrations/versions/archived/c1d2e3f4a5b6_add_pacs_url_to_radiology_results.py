"""add_pacs_url_to_radiology_results

Revision ID: c1d2e3f4a5b6
Revises: b1c2d3e4f5a6
Create Date: 2026-01-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c1d2e3f4a5b6'
down_revision = 'b1c2d3e4f5a6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('radiology_results', sa.Column('pacs_url', sa.String(length=300), nullable=True))


def downgrade():
    op.drop_column('radiology_results', 'pacs_url')
