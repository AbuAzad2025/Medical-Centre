"""Tests for S0-004 limit enforcement and LegacyEntitlementAdapter."""

from datetime import datetime, timedelta, timezone

import pytest

from app.extensions import db
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
from app.core.tenant.models import ProductBundle, Tenant, TenantStatus
from app.core.module.models import TenantModule


@pytest.fixture(scope='function')
def limit_tenant(app):
    t = Tenant(
        slug=f"lim-{datetime.now(timezone.utc).timestamp()}",
        name='Limit Tenant',
        contact_email='lim@test.local',
        status=TenantStatus.ACTIVE,
        product_profile_code='standalone_clinic',
    )
    db.session.add(t)
    db.session.commit()
    yield t
    db.session.delete(t)
    db.session.commit()


class TestLegacyAdapter:
    def test_entitled_via_product_bundle_modules(self, limit_tenant):
        bundle = ProductBundle.query.filter_by(profile_code='standalone_clinic').first()
        if bundle is None:
            pytest.skip('no standalone_clinic bundle seeded')
        mods = bundle.get_modules()
        if not mods:
            pytest.skip('bundle has no modules')
        from app.core.module.registry import MODULE_REGISTRY
        cap = MODULE_REGISTRY[mods[0]].capabilities[0]
        assert LegacyEntitlementAdapter.is_entitled(limit_tenant, cap) is True

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
        ver = PackageVersion(package_id=pkg.id, version='1.0.0', published_at=datetime.now(timezone.utc))
        db.session.add(ver)
        db.session.flush()
        db.session.add(PackageVersionLimit(package_version_id=ver.id, limit_key='max_users', limit_value=2))
        db.session.add(PackageVersionLimit(package_version_id=ver.id, limit_key='max_patients', limit_value=5))
        db.session.add(PackageVersionEntitlement(
            package_version_id=ver.id, module_name='lab', capability_key='lab.order'))
        line = SubscriptionLine(
            tenant_id=tenant_id,
            package_version_id=ver.id,
            line_type=SubscriptionLineType.BASE,
            status=SubscriptionLineStatus.ACTIVE,
            billing_type='monthly',
            unit_price=100,
            effective_from=datetime.now(timezone.utc) - timedelta(days=1),
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
            effective_from=datetime.now(timezone.utc) - timedelta(hours=1),
            is_effective=True,
            calculated_at=datetime.now(timezone.utc),
            calculation_version=1,
        )
        db.session.add(te)
        db.session.commit()
        assert EntitlementResolver.is_entitled(limit_tenant.id, 'lab.order', audit=False) is True

    def test_storage_limit_warn_only(self, limit_tenant):
        self._package_line(limit_tenant.id)
        ok, _ = EntitlementResolver.check_limit(limit_tenant.id, 'storage_gb', 99999, increment=1)
        assert ok is True
