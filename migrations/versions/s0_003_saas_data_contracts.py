"""S0-003: SaaS data contracts (packages, subscriptions, entitlements).

Revision ID: s0_003_saas_data_contracts
Revises: s0_000_product_profile_string
Create Date: 2026-06-22
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 's0_003_saas_data_contracts'
down_revision = 's0_000_product_profile_string'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.create_table(
        'packages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('name_ar', sa.String(length=100), nullable=True),
        sa.Column('slug', sa.String(length=50), nullable=False),
        sa.Column('category', sa.String(length=20), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug'),
        sa.CheckConstraint("category IN ('bundle', 'addon', 'standalone')",
                           name='chk_package_category'),
    )
    op.create_index('ix_packages_slug', 'packages', ['slug'], unique=False)
    op.create_index('ix_packages_category', 'packages', ['category'], unique=False)
    op.create_index('ix_packages_is_active', 'packages', ['is_active'], unique=False)

    op.create_table(
        'package_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('package_id', sa.Integer(), nullable=False),
        sa.Column('version', sa.String(length=20), nullable=False),
        sa.Column('changelog', sa.Text(), nullable=True),
        sa.Column('is_deprecated', sa.Boolean(), nullable=False),
        sa.Column('retirement_date', sa.Date(), nullable=True),
        sa.Column('published_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['package_id'], ['packages.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('package_id', 'version', name='uq_package_version'),
    )
    op.create_index('ix_package_versions_package_id', 'package_versions', ['package_id'],
                    unique=False)

    op.create_table(
        'package_version_entitlements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('package_version_id', sa.Integer(), nullable=False),
        sa.Column('module_name', sa.String(length=50), nullable=False),
        sa.Column('capability_key', sa.String(length=80), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['package_version_id'], ['package_versions.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_pve_package_version_id', 'package_version_entitlements',
                    ['package_version_id'], unique=False)
    op.create_index('ix_pve_module_name', 'package_version_entitlements', ['module_name'],
                    unique=False)
    op.create_index('ix_pve_capability_key', 'package_version_entitlements', ['capability_key'],
                    unique=False)

    op.create_table(
        'package_version_limits',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('package_version_id', sa.Integer(), nullable=False),
        sa.Column('limit_key', sa.String(length=50), nullable=False),
        sa.Column('limit_value', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['package_version_id'], ['package_versions.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('limit_value IS NULL OR limit_value >= 0',
                           name='chk_package_version_limit_value_non_negative'),
    )
    op.create_index('ix_pvl_package_version_id', 'package_version_limits',
                    ['package_version_id'], unique=False)
    op.create_index('ix_pvl_limit_key', 'package_version_limits', ['limit_key'], unique=False)

    op.create_table(
        'package_version_pricing',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('package_version_id', sa.Integer(), nullable=False),
        sa.Column('billing_type', sa.String(length=10), nullable=False),
        sa.Column('price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('setup_fee', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.ForeignKeyConstraint(['package_version_id'], ['package_versions.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("billing_type IN ('monthly', 'yearly')",
                           name='chk_package_version_pricing_billing_type'),
        sa.CheckConstraint('price >= 0', name='chk_package_version_pricing_price_non_negative'),
        sa.CheckConstraint('setup_fee >= 0',
                           name='chk_package_version_pricing_setup_fee_non_negative'),
    )
    op.create_index('ix_pvp_package_version_id', 'package_version_pricing',
                    ['package_version_id'], unique=False)
    op.create_index('ix_pvp_billing_type', 'package_version_pricing', ['billing_type'],
                    unique=False)

    op.create_table(
        'subscription_lines',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('package_version_id', sa.Integer(), nullable=False),
        sa.Column('line_type', sa.String(length=10), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('billing_type', sa.String(length=10), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('unit_price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('trial_end', sa.Date(), nullable=True),
        sa.Column('effective_from', sa.DateTime(timezone=True), nullable=False),
        sa.Column('effective_to', sa.DateTime(timezone=True), nullable=True),
        sa.Column('current_period_start', sa.Date(), nullable=True),
        sa.Column('current_period_end', sa.Date(), nullable=True),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancellation_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['package_version_id'], ['package_versions.id'],
                                ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("line_type IN ('base', 'addon')",
                           name='chk_subscription_line_type'),
        sa.CheckConstraint("status IN ('scheduled', 'active', 'ended')",
                           name='chk_subscription_line_status'),
        sa.CheckConstraint("billing_type IN ('monthly', 'yearly')",
                           name='chk_subscription_line_billing_type'),
        sa.CheckConstraint('quantity > 0', name='chk_subscription_line_quantity_positive'),
        sa.CheckConstraint('unit_price >= 0',
                           name='chk_subscription_line_unit_price_non_negative'),
    )
    op.create_index('ix_subscription_lines_tenant_id', 'subscription_lines', ['tenant_id'],
                    unique=False)
    op.create_index('ix_subscription_lines_package_version_id', 'subscription_lines',
                    ['package_version_id'], unique=False)
    op.create_index('ix_subscription_lines_tenant_status', 'subscription_lines',
                    ['tenant_id', 'status'], unique=False)
    op.create_index('ix_subscription_lines_tenant_type', 'subscription_lines',
                    ['tenant_id', 'line_type'], unique=False)

    op.execute(
        "ALTER TABLE subscription_lines DROP CONSTRAINT IF EXISTS subscription_lines_no_base_overlap"
    )
    op.execute(
        "ALTER TABLE subscription_lines ADD CONSTRAINT subscription_lines_no_base_overlap "
        "EXCLUDE USING gist ("
        "tenant_id WITH =, "
        "tstzrange(effective_from, COALESCE(effective_to, 'infinity'::timestamptz), '[)') WITH &&"
        ") WHERE (line_type = 'base' AND status IN ('scheduled', 'active'))"
    )

    op.create_table(
        'package_version_availability',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('package_version_id', sa.Integer(), nullable=False),
        sa.Column('availability_status', sa.String(length=20), nullable=False),
        sa.Column('effective_from', sa.DateTime(), nullable=False),
        sa.Column('effective_to', sa.DateTime(), nullable=True),
        sa.Column('deprecation_reason', sa.Text(), nullable=True),
        sa.Column('retirement_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['package_version_id'], ['package_versions.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "availability_status IN ('available', 'deprecated', 'retired')",
            name='chk_package_version_availability_status'
        ),
    )
    op.create_index('ix_pva_package_version_id', 'package_version_availability',
                    ['package_version_id'], unique=False)
    op.create_index('ix_pva_availability_status', 'package_version_availability',
                    ['availability_status'], unique=False)

    op.create_table(
        'tenant_overrides',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('module_name', sa.String(length=50), nullable=False),
        sa.Column('capability_key', sa.String(length=80), nullable=False),
        sa.Column('override_type', sa.String(length=10), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('granted_by', sa.Integer(), nullable=True),
        sa.Column('effective_from', sa.DateTime(), nullable=False),
        sa.Column('effective_to', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['granted_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("override_type IN ('grant', 'revoke')",
                           name='chk_tenant_override_type'),
    )
    op.create_index('ix_tenant_overrides_tenant_id', 'tenant_overrides', ['tenant_id'],
                    unique=False)
    op.create_index('ix_tenant_overrides_tenant_capability', 'tenant_overrides',
                    ['tenant_id', 'capability_key'], unique=False)

    op.create_table(
        'enterprise_contracts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('contract_ref', sa.String(length=100), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('signed_by', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_enterprise_contracts_tenant_id', 'enterprise_contracts', ['tenant_id'],
                    unique=False)
    op.create_index('ix_enterprise_contracts_contract_ref', 'enterprise_contracts',
                    ['contract_ref'], unique=False)

    op.create_table(
        'enterprise_contract_entitlements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('enterprise_contract_id', sa.Integer(), nullable=False),
        sa.Column('capability_key', sa.String(length=80), nullable=False),
        sa.Column('effective_from', sa.DateTime(), nullable=False),
        sa.Column('effective_to', sa.DateTime(), nullable=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('revoke_reason', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['enterprise_contract_id'], ['enterprise_contracts.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ece_contract_id', 'enterprise_contract_entitlements',
                    ['enterprise_contract_id'], unique=False)
    op.create_index('ix_ece_capability_key', 'enterprise_contract_entitlements',
                    ['capability_key'], unique=False)

    op.create_table(
        'entitlement_grants',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('capability_key', sa.String(length=80), nullable=False),
        sa.Column('subscription_line_id', sa.Integer(), nullable=True),
        sa.Column('tenant_override_id', sa.Integer(), nullable=True),
        sa.Column('tenant_feature_flag_id', sa.Integer(), nullable=True),
        sa.Column('enterprise_contract_entitlement_id', sa.Integer(), nullable=True),
        sa.Column('effective_from', sa.DateTime(), nullable=False),
        sa.Column('effective_to', sa.DateTime(), nullable=True),
        sa.Column('granted_by_user_id', sa.Integer(), nullable=True),
        sa.Column('revoked_by_user_id', sa.Integer(), nullable=True),
        sa.Column('revocation_reason', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subscription_line_id'], ['subscription_lines.id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_override_id'], ['tenant_overrides.id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_feature_flag_id'], ['tenant_feature_flags.id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['enterprise_contract_entitlement_id'],
                                ['enterprise_contract_entitlements.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['granted_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['revoked_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "(subscription_line_id IS NOT NULL)::int + "
            "(tenant_override_id IS NOT NULL)::int + "
            "(tenant_feature_flag_id IS NOT NULL)::int + "
            "(enterprise_contract_entitlement_id IS NOT NULL)::int = 1",
            name='chk_entitlement_grant_single_source'
        ),
    )
    op.create_index('ix_entitlement_grants_tenant_id', 'entitlement_grants', ['tenant_id'],
                    unique=False)
    op.create_index('ix_entitlement_grants_tenant_capability', 'entitlement_grants',
                    ['tenant_id', 'capability_key'], unique=False)

    op.create_table(
        'tenant_entitlements',
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('capability_key', sa.String(length=80), nullable=False),
        sa.Column('module_name', sa.String(length=50), nullable=True),
        sa.Column('effective_from', sa.DateTime(), nullable=False),
        sa.Column('effective_to', sa.DateTime(), nullable=True),
        sa.Column('is_effective', sa.Boolean(), nullable=False),
        sa.Column('source_summary', sa.Text(), nullable=True),
        sa.Column('calculated_at', sa.DateTime(), nullable=False),
        sa.Column('calculation_version', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('tenant_id', 'capability_key'),
    )
    op.create_index('ix_tenant_entitlements_tenant_effective', 'tenant_entitlements',
                    ['tenant_id', 'is_effective'], unique=False)


def downgrade() -> None:
    op.drop_table('tenant_entitlements')
    op.drop_table('entitlement_grants')
    op.drop_table('enterprise_contract_entitlements')
    op.drop_table('enterprise_contracts')
    op.drop_table('tenant_overrides')
    op.drop_table('package_version_availability')
    op.execute(
        "ALTER TABLE subscription_lines DROP CONSTRAINT IF EXISTS subscription_lines_no_base_overlap"
    )
    op.drop_table('subscription_lines')
    op.drop_table('package_version_pricing')
    op.drop_table('package_version_limits')
    op.drop_table('package_version_entitlements')
    op.drop_table('package_versions')
    op.drop_table('packages')
