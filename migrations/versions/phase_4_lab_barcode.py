"""
Phase 4: Add barcode, collection_time, received_time, analyzed_by to lab_requests.

Revision ID: phase_4_lab_barcode
Revises: phase_3_lab_test_catalog
Create Date: 2026-06-21
"""
from alembic import op
import sqlalchemy as sa

revision = 'phase_4_lab_barcode'
down_revision = 'phase_3_lab_test_catalog'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('lab_requests') as batch_op:
        batch_op.add_column(sa.Column('barcode', sa.String(100), nullable=True, unique=True))
        batch_op.add_column(sa.Column('barcode_image', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('collection_time', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('received_time', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('analyzed_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True))
        batch_op.create_index('ix_lab_requests_barcode', ['barcode'])
        batch_op.create_index('ix_lab_requests_analyzed_by', ['analyzed_by'])


def downgrade():
    with op.batch_alter_table('lab_requests') as batch_op:
        batch_op.drop_index('ix_lab_requests_analyzed_by')
        batch_op.drop_index('ix_lab_requests_barcode')
        batch_op.drop_column('analyzed_by')
        batch_op.drop_column('received_time')
        batch_op.drop_column('collection_time')
        batch_op.drop_column('barcode_image')
        batch_op.drop_column('barcode')
