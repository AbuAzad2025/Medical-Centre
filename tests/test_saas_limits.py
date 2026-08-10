"""Tests for S0-004 limit enforcement and LegacyEntitlementAdapter."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.module.models import TenantModule
from app.core.saas.exceptions import EntitlementDeniedError
from app.core.saas.legacy_adapter import LegacyEntitlementAdapter
from app.core.saas.models import (
    Package,
    PackageVersion,
    PackageVersionEntitlement,
    PackageVersionLimit,
    SubscriptionLine,
    SubscriptionLineStatus,
    SubscriptionLineType,
    TenantEntitlement,
)
from app.core.saas.resolver import EntitlementResolver
from app.core.tenant.models import ProductBundle, Tenant, TenantStatus, get_bundle_for_profile
from app.extensions import db
from tests.tenant_context import tenant_test_context


@pytest.fixture(scope='function')
def limit_tenant(app):
    t = Tenant(
        slug=f'lim-{datetime.now(UTC).timestamp()}',
        name='Limit Tenant',
        contact_email='lim@test.local',
        status=TenantStatus.ACTIVE,
        product_profile_code='doctor_clinic_full',
    )
    db.session.add(t)
    db.session.commit()
    with tenant_test_context(app, t):
        yield t
        db.session.delete(t)
        db.session.commit()


class TestLegacyAdapter:
    def test_entitled_via_product_bundle_modules(self, limit_tenant):
        # Self-seed the bundles this test depends on instead of skipping when
        # CI does not seed ProductBundles. 'doctor_clinic_full' is the profile
        # of the limit_tenant fixture; the legacy adapter resolves the
        # tenant's own bundle through get_bundle_for_profile().
        # Clean up any leftover test bundles from previous runs to stay deterministic.
        for stale in db.session.execute(
            select(ProductBundle).filter(
                ProductBundle.slug.in_(['standalone-clinic-test', 'doctor-clinic-full-test'])
            )
        ).scalars():
            db.session.delete(stale)
        db.session.commit()
        bundle = ProductBundle(
            name='Standalone Clinic',
            name_ar='عيادة مستقلة',
            slug='standalone-clinic-test',
            description_ar='Test-seeded bundle',
            profile_code='standalone_clinic',
        )
        bundle.set_modules(['doctor'])
        db.session.add(bundle)
        tenant_bundle = ProductBundle(
            name='Doctor Clinic Full',
            name_ar='عيادة طبيب كاملة',
            slug='doctor-clinic-full-test',
            description_ar='Test-seeded bundle',
            profile_code='doctor_clinic_full',
        )
        tenant_bundle.set_modules(['doctor'])
        db.session.add(tenant_bundle)
        db.session.commit()
        try:
            mods = bundle.get_modules()
            assert mods, 'bundle must expose at least one module'
            from app.core.module.registry import MODULE_REGISTRY

            cap = MODULE_REGISTRY[mods[0]].capabilities[0]
            assert LegacyEntitlementAdapter.is_entitled(limit_tenant, cap) is True
        finally:
            # Clean up so later tests are not affected by our seeded bundles.
            for stale in db.session.execute(
                select(ProductBundle).filter(
                    ProductBundle.slug.in_(['standalone-clinic-test', 'doctor-clinic-full-test'])
                )
            ).scalars():
                db.session.delete(stale)
            db.session.commit()

    def test_get_limits_from_bundle(self, limit_tenant):
        limits = LegacyEntitlementAdapter.get_limits(limit_tenant.id)
        if limits:
            assert 'max_users' in limits or 'max_patients' in limits

    def test_tenant_module_grants_capability(self, limit_tenant):
        db.session.add(TenantModule(tenant_id=limit_tenant.id, module_name='lab', is_active=True))
        db.session.commit()
        assert LegacyEntitlementAdapter.is_entitled(limit_tenant, 'lab_order') is True


class TestEntitlementResolverLimits:
    def _package_line(self, tenant_id):
        pkg = Package(name='LimPkg', slug=f'lim-{tenant_id}', category='bundle', is_active=True)
        db.session.add(pkg)
        db.session.flush()
        ver = PackageVersion(package_id=pkg.id, version='1.0.0', published_at=datetime.now(UTC))
        db.session.add(ver)
        db.session.flush()
        db.session.add(
            PackageVersionLimit(package_version_id=ver.id, limit_key='max_users', limit_value=2)
        )
        db.session.add(
            PackageVersionLimit(package_version_id=ver.id, limit_key='max_patients', limit_value=5)
        )
        db.session.add(
            PackageVersionEntitlement(
                package_version_id=ver.id, module_name='lab', capability_key='lab.order'
            )
        )
        line = SubscriptionLine(
            tenant_id=tenant_id,
            package_version_id=ver.id,
            line_type=SubscriptionLineType.BASE,
            status=SubscriptionLineStatus.ACTIVE,
            billing_type='monthly',
            unit_price=100,
            effective_from=datetime.now(UTC) - timedelta(days=1),
        )
        db.session.add(line)
        db.session.commit()
        return ver

    def test_limits_from_subscription_line(self, limit_tenant):
        self._package_line(limit_tenant.id)
        limits = EntitlementResolver.get_effective_limits(limit_tenant.id)
        assert limits.get('max_users') == 2
        assert limits.get('max_patients') == 5

    def test_check_limit_blocks_over_cap(self, limit_tenant):
        self._package_line(limit_tenant.id)
        ok, reason = EntitlementResolver.check_limit(limit_tenant.id, 'max_users', 2, increment=1)
        assert ok is False
        assert 'max_users' in reason

    def test_assert_within_limit_raises(self, limit_tenant):
        self._package_line(limit_tenant.id)
        with pytest.raises(EntitlementDeniedError):
            EntitlementResolver.assert_within_limit(limit_tenant.id, 'max_users', 5)

    def test_legacy_fallback_when_no_projection(self, limit_tenant):
        db.session.add(TenantModule(tenant_id=limit_tenant.id, module_name='lab', is_active=True))
        db.session.commit()
        assert EntitlementResolver.is_entitled(limit_tenant.id, 'lab_order', audit=False) is True

    def test_projection_takes_precedence(self, limit_tenant):
        te = TenantEntitlement(
            tenant_id=limit_tenant.id,
            capability_key='lab.order',
            module_name='lab',
            effective_from=datetime.now(UTC) - timedelta(hours=1),
            is_effective=True,
            calculated_at=datetime.now(UTC),
            calculation_version=1,
        )
        db.session.add(te)
        db.session.commit()
        assert EntitlementResolver.is_entitled(limit_tenant.id, 'lab.order', audit=False) is True

    def test_storage_limit_warn_only(self, limit_tenant):
        self._package_line(limit_tenant.id)
        ok, _ = EntitlementResolver.check_limit(limit_tenant.id, 'storage_gb', 99999, increment=1)
        assert ok is True
