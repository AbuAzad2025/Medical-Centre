"""add_med_supply_requests_and_drug_interactions

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-01-21 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'medication_supply_requests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('request_number', sa.String(length=40), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='DRAFT'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('approved_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('fulfilled_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('fulfilled_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('DRAFT','APPROVED','FULFILLED','CANCELLED')", name='chk_med_supply_requests_status'),
        sa.UniqueConstraint('request_number', name='uq_med_supply_requests_number'),
    )
    op.create_index('ix_medication_supply_requests_request_number', 'medication_supply_requests', ['request_number'], unique=True)
    op.create_index('ix_medication_supply_requests_status', 'medication_supply_requests', ['status'], unique=False)
    op.create_index('ix_medication_supply_requests_created_by', 'medication_supply_requests', ['created_by'], unique=False)
    op.create_index('ix_medication_supply_requests_approved_by', 'medication_supply_requests', ['approved_by'], unique=False)
    op.create_index('ix_medication_supply_requests_fulfilled_by', 'medication_supply_requests', ['fulfilled_by'], unique=False)
    op.create_index('ix_medication_supply_requests_created_at', 'medication_supply_requests', ['created_at'], unique=False)
    op.create_index('idx_med_supply_requests_status_created', 'medication_supply_requests', ['status', 'created_at'], unique=False)

    op.create_table(
        'medication_supply_request_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('request_id', sa.Integer(), sa.ForeignKey('medication_supply_requests.id', ondelete='CASCADE'), nullable=False),
        sa.Column('medication_id', sa.Integer(), sa.ForeignKey('medications.id', ondelete='CASCADE'), nullable=False),
        sa.Column('current_stock', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('minimum_stock', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('requested_qty', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('approved_qty', sa.Integer(), nullable=True),
        sa.Column('fulfilled_qty', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("requested_qty > 0", name='chk_med_supply_request_items_requested_qty'),
    )
    op.create_index('ix_medication_supply_request_items_request_id', 'medication_supply_request_items', ['request_id'], unique=False)
    op.create_index('ix_medication_supply_request_items_medication_id', 'medication_supply_request_items', ['medication_id'], unique=False)
    op.create_index('ix_medication_supply_request_items_created_at', 'medication_supply_request_items', ['created_at'], unique=False)
    op.create_index('idx_med_supply_request_items_request_med', 'medication_supply_request_items', ['request_id', 'medication_id'], unique=False)

    op.create_table(
        'drug_interactions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('medication_a_id', sa.Integer(), sa.ForeignKey('medications.id', ondelete='CASCADE'), nullable=False),
        sa.Column('medication_b_id', sa.Integer(), sa.ForeignKey('medications.id', ondelete='CASCADE'), nullable=False),
        sa.Column('severity', sa.String(length=16), nullable=False, server_default='MODERATE'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("severity IN ('LOW','MODERATE','HIGH')", name='chk_drug_interactions_severity'),
        sa.UniqueConstraint('medication_a_id', 'medication_b_id', name='uq_drug_interactions_pair'),
    )
    op.create_index('ix_drug_interactions_medication_a_id', 'drug_interactions', ['medication_a_id'], unique=False)
    op.create_index('ix_drug_interactions_medication_b_id', 'drug_interactions', ['medication_b_id'], unique=False)
    op.create_index('ix_drug_interactions_severity', 'drug_interactions', ['severity'], unique=False)
    op.create_index('ix_drug_interactions_is_active', 'drug_interactions', ['is_active'], unique=False)
    op.create_index('ix_drug_interactions_created_by', 'drug_interactions', ['created_by'], unique=False)
    op.create_index('ix_drug_interactions_created_at', 'drug_interactions', ['created_at'], unique=False)
    op.create_index('idx_drug_interactions_active_severity', 'drug_interactions', ['is_active', 'severity'], unique=False)


def downgrade():
    op.drop_index('idx_drug_interactions_active_severity', table_name='drug_interactions')
    op.drop_index('ix_drug_interactions_created_at', table_name='drug_interactions')
    op.drop_index('ix_drug_interactions_created_by', table_name='drug_interactions')
    op.drop_index('ix_drug_interactions_is_active', table_name='drug_interactions')
    op.drop_index('ix_drug_interactions_severity', table_name='drug_interactions')
    op.drop_index('ix_drug_interactions_medication_b_id', table_name='drug_interactions')
    op.drop_index('ix_drug_interactions_medication_a_id', table_name='drug_interactions')
    op.drop_table('drug_interactions')

    op.drop_index('idx_med_supply_request_items_request_med', table_name='medication_supply_request_items')
    op.drop_index('ix_medication_supply_request_items_created_at', table_name='medication_supply_request_items')
    op.drop_index('ix_medication_supply_request_items_medication_id', table_name='medication_supply_request_items')
    op.drop_index('ix_medication_supply_request_items_request_id', table_name='medication_supply_request_items')
    op.drop_table('medication_supply_request_items')

    op.drop_index('idx_med_supply_requests_status_created', table_name='medication_supply_requests')
    op.drop_index('ix_medication_supply_requests_created_at', table_name='medication_supply_requests')
    op.drop_index('ix_medication_supply_requests_fulfilled_by', table_name='medication_supply_requests')
    op.drop_index('ix_medication_supply_requests_approved_by', table_name='medication_supply_requests')
    op.drop_index('ix_medication_supply_requests_created_by', table_name='medication_supply_requests')
    op.drop_index('ix_medication_supply_requests_status', table_name='medication_supply_requests')
    op.drop_index('ix_medication_supply_requests_request_number', table_name='medication_supply_requests')
    op.drop_table('medication_supply_requests')

