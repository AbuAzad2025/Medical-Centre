"""add_slow_query_reports

Revision ID: 9c0d1e2f3a4b
Revises: 8b9c0d1e2f3a
Create Date: 2026-01-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '9c0d1e2f3a4b'
down_revision = '8b9c0d1e2f3a'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'slow_query_reports',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('reset_time', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('idx_slow_query_report_period', 'slow_query_reports', ['period_start', 'period_end'], unique=False)
    op.create_index('idx_slow_query_report_created', 'slow_query_reports', ['created_at'], unique=False)

    op.create_table(
        'slow_query_entries',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('report_id', sa.Integer(), sa.ForeignKey('slow_query_reports.id', ondelete='CASCADE'), nullable=False),
        sa.Column('query', sa.Text(), nullable=False),
        sa.Column('calls', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_time', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('mean_time', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('rows', sa.Integer(), nullable=False, server_default='0'),
    )
    op.create_index('idx_slow_query_entry_report', 'slow_query_entries', ['report_id'], unique=False)
    op.create_index('idx_slow_query_entry_mean', 'slow_query_entries', ['mean_time'], unique=False)


def downgrade():
    op.drop_index('idx_slow_query_entry_mean', table_name='slow_query_entries')
    op.drop_index('idx_slow_query_entry_report', table_name='slow_query_entries')
    op.drop_table('slow_query_entries')
    op.drop_index('idx_slow_query_report_created', table_name='slow_query_reports')
    op.drop_index('idx_slow_query_report_period', table_name='slow_query_reports')
    op.drop_table('slow_query_reports')
