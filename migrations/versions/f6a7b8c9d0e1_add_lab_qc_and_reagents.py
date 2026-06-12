"""add_lab_qc_and_reagents

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-01-21 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = 'f6a7b8c9d0e1'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'lab_quality_control_entries',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('test_code', sa.String(length=50), nullable=False),
        sa.Column('test_name', sa.String(length=120), nullable=True),
        sa.Column('control_level', sa.String(length=16), nullable=False, server_default='NORMAL'),
        sa.Column('measured_value', sa.String(length=120), nullable=False),
        sa.Column('unit', sa.String(length=40), nullable=True),
        sa.Column('expected_range', sa.String(length=120), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='PASS'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('recorded_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('recorded_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("control_level IN ('LOW','NORMAL','HIGH')", name='chk_lab_qc_control_level'),
        sa.CheckConstraint("status IN ('PASS','FAIL')", name='chk_lab_qc_status'),
    )
    op.create_index('ix_lab_quality_control_entries_test_code', 'lab_quality_control_entries', ['test_code'], unique=False)
    op.create_index('ix_lab_quality_control_entries_control_level', 'lab_quality_control_entries', ['control_level'], unique=False)
    op.create_index('ix_lab_quality_control_entries_status', 'lab_quality_control_entries', ['status'], unique=False)
    op.create_index('ix_lab_quality_control_entries_recorded_by', 'lab_quality_control_entries', ['recorded_by'], unique=False)
    op.create_index('ix_lab_quality_control_entries_recorded_at', 'lab_quality_control_entries', ['recorded_at'], unique=False)
    op.create_index('idx_lab_qc_test_date', 'lab_quality_control_entries', ['test_code', 'recorded_at'], unique=False)

    op.create_table(
        'lab_reagents',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('supplier', sa.String(length=120), nullable=True),
        sa.Column('lot_number', sa.String(length=80), nullable=True),
        sa.Column('unit', sa.String(length=40), nullable=True),
        sa.Column('stock_quantity', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('minimum_stock', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('expiry_date', sa.Date(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_lab_reagents_name', 'lab_reagents', ['name'], unique=False)
    op.create_index('ix_lab_reagents_lot_number', 'lab_reagents', ['lot_number'], unique=False)
    op.create_index('ix_lab_reagents_stock_quantity', 'lab_reagents', ['stock_quantity'], unique=False)
    op.create_index('ix_lab_reagents_minimum_stock', 'lab_reagents', ['minimum_stock'], unique=False)
    op.create_index('ix_lab_reagents_expiry_date', 'lab_reagents', ['expiry_date'], unique=False)
    op.create_index('ix_lab_reagents_is_active', 'lab_reagents', ['is_active'], unique=False)
    op.create_index('ix_lab_reagents_created_at', 'lab_reagents', ['created_at'], unique=False)
    op.create_index('ix_lab_reagents_updated_at', 'lab_reagents', ['updated_at'], unique=False)
    op.create_index('idx_lab_reagents_stock', 'lab_reagents', ['is_active', 'stock_quantity'], unique=False)
    op.create_index('idx_lab_reagents_expiry', 'lab_reagents', ['is_active', 'expiry_date'], unique=False)


def downgrade():
    op.drop_index('idx_lab_reagents_expiry', table_name='lab_reagents')
    op.drop_index('idx_lab_reagents_stock', table_name='lab_reagents')
    op.drop_index('ix_lab_reagents_updated_at', table_name='lab_reagents')
    op.drop_index('ix_lab_reagents_created_at', table_name='lab_reagents')
    op.drop_index('ix_lab_reagents_is_active', table_name='lab_reagents')
    op.drop_index('ix_lab_reagents_expiry_date', table_name='lab_reagents')
    op.drop_index('ix_lab_reagents_minimum_stock', table_name='lab_reagents')
    op.drop_index('ix_lab_reagents_stock_quantity', table_name='lab_reagents')
    op.drop_index('ix_lab_reagents_lot_number', table_name='lab_reagents')
    op.drop_index('ix_lab_reagents_name', table_name='lab_reagents')
    op.drop_table('lab_reagents')

    op.drop_index('idx_lab_qc_test_date', table_name='lab_quality_control_entries')
    op.drop_index('ix_lab_quality_control_entries_recorded_at', table_name='lab_quality_control_entries')
    op.drop_index('ix_lab_quality_control_entries_recorded_by', table_name='lab_quality_control_entries')
    op.drop_index('ix_lab_quality_control_entries_status', table_name='lab_quality_control_entries')
    op.drop_index('ix_lab_quality_control_entries_control_level', table_name='lab_quality_control_entries')
    op.drop_index('ix_lab_quality_control_entries_test_code', table_name='lab_quality_control_entries')
    op.drop_table('lab_quality_control_entries')

