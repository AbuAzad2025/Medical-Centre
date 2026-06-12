"""Add tenant, module, subscription, and stock movement tables

Revision ID: tenant_module_stock_2026
Revises: 
Create Date: 2026-06-12 00:05:10
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'tenant_module_stock_2026'
down_revision = 'c1d2e3f4a5b6'
branch_labels = None
depends_on = None


def upgrade():
    # tenants
    op.create_table(
        'tenants',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('slug', sa.String(80), nullable=False, unique=True, index=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('name_ar', sa.String(200), nullable=True),
        sa.Column('domain', sa.String(255), nullable=True, index=True),
        sa.Column('subdomain', sa.String(80), nullable=True, unique=True, index=True),
        sa.Column('contact_email', sa.String(120), nullable=False),
        sa.Column('contact_phone', sa.String(20), nullable=True),
        sa.Column('tax_number', sa.String(50), nullable=True),
        sa.Column('status', sa.Enum('active','suspended','pending','expired','deleted', name='tenantstatus'), nullable=False, server_default='pending'),
        sa.Column('storage_mode', sa.Enum('cloud','local','hybrid', name='storagemode'), nullable=False, server_default='local'),
        sa.Column('subscription_type', sa.Enum('perpetual','monthly','yearly', name='subscriptiontype'), nullable=True),
        sa.Column('subscription_start', sa.Date(), nullable=True),
        sa.Column('subscription_end', sa.Date(), nullable=True),
        sa.Column('grace_period_end', sa.Date(), nullable=True),
        sa.Column('plan_id', sa.Integer(), nullable=True),
        sa.Column('logo_url', sa.String(255), nullable=True),
        sa.Column('primary_color', sa.String(7), server_default='#0d6efd', nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    # subscription_plans
    op.create_table(
        'subscription_plans',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('name_ar', sa.String(100), nullable=True),
        sa.Column('billing_type', sa.Enum('perpetual','monthly','yearly', name='subscriptiontype'), nullable=False),
        sa.Column('base_price', sa.Numeric(12, 2), nullable=False),
        sa.Column('currency', sa.String(3), server_default='SAR', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('modules_included', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )

    # Add FK from tenants to subscription_plans
    op.create_foreign_key('fk_tenants_plan', 'tenants', 'subscription_plans', ['plan_id'], ['id'])

    # tenant_subscription_history
    op.create_table(
        'tenant_subscription_history',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), nullable=False, index=True),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('old_plan_id', sa.Integer(), nullable=True),
        sa.Column('new_plan_id', sa.Integer(), nullable=True),
        sa.Column('amount_paid', sa.Numeric(12, 2), nullable=True),
        sa.Column('performed_by', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_foreign_key('fk_tsh_tenant', 'tenant_subscription_history', 'tenants', ['tenant_id'], ['id'], ondelete='CASCADE')

    # module_definitions
    op.create_table(
        'module_definitions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(50), nullable=False, unique=True, index=True),
        sa.Column('name_ar', sa.String(100), nullable=False),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )

    # tenant_modules
    op.create_table(
        'tenant_modules',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), nullable=False, index=True),
        sa.Column('module_name', sa.String(50), nullable=False, index=True),
        sa.Column('is_active', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('activated_at', sa.DateTime(), nullable=True),
        sa.Column('deactivated_at', sa.DateTime(), nullable=True),
        sa.Column('activated_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('tenant_id', 'module_name', name='uq_tenant_module'),
    )
    op.create_foreign_key('fk_tm_tenant', 'tenant_modules', 'tenants', ['tenant_id'], ['id'], ondelete='CASCADE')

    # stock_movements
    op.create_table(
        'stock_movements',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('medication_id', sa.Integer(), nullable=False, index=True),
        sa.Column('movement_type', sa.String(20), nullable=False, index=True),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('before_quantity', sa.Integer(), nullable=False),
        sa.Column('after_quantity', sa.Integer(), nullable=False),
        sa.Column('reference_type', sa.String(50), nullable=True),
        sa.Column('reference_id', sa.Integer(), nullable=True),
        sa.Column('batch_number', sa.String(100), nullable=True),
        sa.Column('expiry_date', sa.Date(), nullable=True),
        sa.Column('performed_by', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, index=True),
    )

    # Add tenant_id to users
    op.add_column('users', sa.Column('tenant_id', sa.Integer(), nullable=True, index=True))
    op.create_foreign_key('fk_users_tenant', 'users', 'tenants', ['tenant_id'], ['id'], ondelete='CASCADE')
    op.create_unique_constraint('uq_user_tenant_username', 'users', ['tenant_id', 'username'])
    op.create_unique_constraint('uq_user_tenant_email', 'users', ['tenant_id', 'email'])
    # Drop old unique constraints (global) if they exist — they break multi-tenancy
    # Note: these may not exist in all installations; wrap in try or use batch_alter_table


def downgrade():
    op.drop_constraint('fk_users_tenant', 'users', type_='foreignkey')
    op.drop_constraint('uq_user_tenant_username', 'users', type_='unique')
    op.drop_constraint('uq_user_tenant_email', 'users', type_='unique')
    op.drop_column('users', 'tenant_id')

    op.drop_table('stock_movements')
    op.drop_table('tenant_modules')
    op.drop_table('module_definitions')
    op.drop_table('tenant_subscription_history')
    op.drop_table('tenants')
    op.drop_table('subscription_plans')
