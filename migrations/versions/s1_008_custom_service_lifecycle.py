"""Add custom service lifecycle fields (Ticket 6)

Revision ID: s1_008_custom_service_lifecycle
Revises: s1_007_rls_phase4
Create Date: 2026-07-02

"""
from alembic import op
import sqlalchemy as sa

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from migration_utils import column_exists, check_constraint_exists


revision = 's1_008_custom_service_lifecycle'
down_revision = 's1_007_rls_phase4'
branch_labels = None
depends_on = None


def upgrade():
    # --- service_master: custom service lifecycle ---
    with op.batch_alter_table('service_master', schema=None) as batch_op:
        if not column_exists('service_master', 'is_custom'):
            batch_op.add_column(sa.Column('is_custom', sa.Boolean(), nullable=True, default=False))
        if not column_exists('service_master', 'approved_by'):
            batch_op.add_column(sa.Column('approved_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True))
        if not column_exists('service_master', 'approved_at'):
            batch_op.add_column(sa.Column('approved_at', sa.DateTime(), nullable=True))
        if not column_exists('service_master', 'created_by'):
            batch_op.add_column(sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True))

    # --- invoice_services: link to source service and creator ---
    with op.batch_alter_table('invoice_services', schema=None) as batch_op:
        if not column_exists('invoice_services', 'service_master_id'):
            batch_op.add_column(sa.Column('service_master_id', sa.Integer(), sa.ForeignKey('service_master.id', ondelete='SET NULL'), nullable=True, index=True))
        if not column_exists('invoice_services', 'created_by'):
            batch_op.add_column(sa.Column('created_by', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True))

    # --- audit_trails: add 'service' to entity_type check constraint ---
    if check_constraint_exists('audit_trails', 'chk_entity_type'):
        op.drop_constraint('chk_entity_type', 'audit_trails', type_='check')
    op.create_check_constraint(
        'chk_entity_type',
        'audit_trails',
        sa.sql.text("entity_type IN ('system', 'user', 'patient', 'visit', 'appointment', 'payment', 'invoice', 'lab_test', 'radiology_test', 'notification', 'role', 'department', 'service')")
    )


def downgrade():
    # --- audit_trails: restore old constraint without 'service' ---
    if check_constraint_exists('audit_trails', 'chk_entity_type'):
        op.drop_constraint('chk_entity_type', 'audit_trails', type_='check')
    op.create_check_constraint(
        'chk_entity_type',
        'audit_trails',
        sa.sql.text("entity_type IN ('system', 'user', 'patient', 'visit', 'appointment', 'payment', 'invoice', 'lab_test', 'radiology_test', 'notification', 'role', 'department')")
    )

    # --- invoice_services ---
    with op.batch_alter_table('invoice_services', schema=None) as batch_op:
        if column_exists('invoice_services', 'created_by'):
            batch_op.drop_column('created_by')
        if column_exists('invoice_services', 'service_master_id'):
            batch_op.drop_column('service_master_id')

    # --- service_master ---
    with op.batch_alter_table('service_master', schema=None) as batch_op:
        if column_exists('service_master', 'created_by'):
            batch_op.drop_column('created_by')
        if column_exists('service_master', 'approved_at'):
            batch_op.drop_column('approved_at')
        if column_exists('service_master', 'approved_by'):
            batch_op.drop_column('approved_by')
        if column_exists('service_master', 'is_custom'):
            batch_op.drop_column('is_custom')
