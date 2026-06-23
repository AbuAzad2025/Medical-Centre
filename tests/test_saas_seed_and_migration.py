"""Tests for S0-006: SaaS business decisions (seed + legacy migration)."""

import uuid

import pytest

from app.extensions import db
from app.core.saas.seed import seed_packages_from_product_bundles
from app.core.saas.migration import migrate_legacy_tenant_to_package, LegacyMigrationError
from app.core.saas.models import (
    Package,
    PackageVersion,
    PackageVersionEntitlement,
    PackageVersionPricing,
    SubscriptionLine,
)
from app.core.saas.resolver import EntitlementResolver
from app.core.tenant.models import ProductBundle, Tenant, TenantStatus


class TestSeedFromProductBundles:
    def test_seed_creates_packages_from_bundles(self, app):
        # Ensure bundles exist
        if ProductBundle.query.count() == 0:
            from app.core.tenant.models import seed_default_bundles
            seed_default_bundles()

        before = Package.query.count()
        created = seed_packages_from_product_bundles()
        # If packages were already seeded in a previous run, assert existing catalog is populated.
        if not created:
            assert before > 0
            package = Package.query.first()
        else:
            assert len(created) > 0
            package = Package.query.get(created[0])

        assert package is not None
        assert package.versions

        if not created:
            version = (
                PackageVersion.query.join(PackageVersionPricing)
                .join(PackageVersionEntitlement)
                .order_by(PackageVersion.id)
                .first()
            )
        else:
            version = PackageVersion.query.filter_by(package_id=package.id).first()

        assert version is not None
        assert version.pricing
        assert PackageVersionEntitlement.query.filter_by(package_version_id=version.id).count() > 0

    def test_seed_is_idempotent(self, app):
        if ProductBundle.query.count() == 0:
            from app.core.tenant.models import seed_default_bundles
            seed_default_bundles()

        first = seed_packages_from_product_bundles()
        count_after_first = Package.query.count()
        second = seed_packages_from_product_bundles()
        count_after_second = Package.query.count()

        assert count_after_first == count_after_second
        assert set(second).issubset(set(first))


class TestLegacyTenantMigration:
    def test_migrate_legacy_tenant_creates_line_and_entitlements(self, app):
        if ProductBundle.query.count() == 0:
            from app.core.tenant.models import seed_default_bundles
            seed_default_bundles()

        created = seed_packages_from_product_bundles()
        if created:
            version = Package.query.get(created[0]).versions[0]
        else:
            version = PackageVersion.query.first()

        tenant = Tenant(
            slug=f"legacy-{uuid.uuid4().hex[:8]}",
            name="Legacy Tenant",
            contact_email="legacy@test.local",
            status=TenantStatus.ACTIVE,
            product_profile_code="custom",
        )
        db.session.add(tenant)
        db.session.commit()

        line = migrate_legacy_tenant_to_package(
            tenant.id,
            package_version_id=version.id,
            billing_type="monthly",
        )

        assert line.tenant_id == tenant.id
        assert line.line_type == "base"
        assert SubscriptionLine.query.filter_by(tenant_id=tenant.id).count() == 1

        capabilities = {e.capability_key for e in version.entitlements}
        for cap in capabilities:
            assert EntitlementResolver.is_entitled(tenant.id, cap) is True

    def test_migrate_fails_if_active_lines_exist(self, app):
        if ProductBundle.query.count() == 0:
            from app.core.tenant.models import seed_default_bundles
            seed_default_bundles()

        created = seed_packages_from_product_bundles()
        if created:
            version = Package.query.get(created[0]).versions[0]
        else:
            version = PackageVersion.query.first()

        tenant = Tenant(
            slug=f"legacy-dup-{uuid.uuid4().hex[:8]}",
            name="Legacy Tenant With Line",
            contact_email="legacy2@test.local",
            status=TenantStatus.ACTIVE,
            product_profile_code="custom",
        )
        db.session.add(tenant)
        db.session.commit()

        migrate_legacy_tenant_to_package(
            tenant.id,
            package_version_id=version.id,
            billing_type="monthly",
        )

        with pytest.raises(LegacyMigrationError):
            migrate_legacy_tenant_to_package(
                tenant.id,
                package_version_id=version.id,
                billing_type="monthly",
            )
