"""Tests for S0-003: SaaS data contracts."""

from datetime import date, datetime, timedelta, timezone
import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app_factory import db as _db
from app.core.saas.models import (
    EnterpriseContract,
    EnterpriseContractEntitlement,
    EntitlementGrant,
    Package,
    PackageVersion,
    PackageVersionAvailability,
    PackageVersionEntitlement,
    PackageVersionLimit,
    PackageVersionPricing,
    SubscriptionLine,
    TenantEntitlement,
    TenantOverride,
)
from app.core.tenant.models import Tenant
from models.user import User


@pytest.fixture(scope='function')
def saas_tenant(app):
    import uuid
    t = Tenant(
        slug=f"saas-{uuid.uuid4().hex[:8]}",
        name='SaaS Test Tenant',
        contact_email='saas-tenant@test.local',
        status='active',
        product_profile_code='standalone_clinic',
    )
    _db.session.add(t)
    _db.session.commit()
    yield t
    _db.session.delete(t)
    _db.session.commit()


@pytest.fixture(scope='function')
def saas_user(app, saas_tenant):
    u = User(
        username=f"saas_admin_{uuid.uuid4().hex[:8]}",
        email='saas@test.local',
        full_name='SaaS Admin',
        role='admin',
        is_active=True,
        tenant_id=saas_tenant.id,
    )
    u.set_password('test123')
    _db.session.add(u)
    _db.session.commit()
    yield u
    _db.session.delete(u)
    _db.session.commit()


@pytest.fixture(scope='function')
def package_bundle(app):
    import uuid
    slug = f"doctor_clinic_full_{uuid.uuid4().hex[:8]}"
    p = Package(
        name='Doctor Clinic Full',
        name_ar='عيادة طبيب متكاملة',
        slug=slug,
        category='bundle',
        is_active=True,
    )
    _db.session.add(p)
    _db.session.commit()
    return p


@pytest.fixture(scope='function')
def package_version(app, package_bundle):
    pv = PackageVersion(
        package_id=package_bundle.id,
        version='1.0.0',
        changelog='Initial version',
        published_at=datetime.now(timezone.utc),
    )
    _db.session.add(pv)
    _db.session.commit()
    return pv


class TestPackageAndVersion:
    def test_create_package_with_version(self, package_bundle, package_version):
        assert package_version.package == package_bundle
        assert package_version.version == '1.0.0'

    def test_version_entitlements_and_limits(self, package_version, saas_tenant):
        ent = PackageVersionEntitlement(
            package_version_id=package_version.id,
            module_name='lab',
            capability_key='lab.order',
        )
        lim = PackageVersionLimit(
            package_version_id=package_version.id,
            limit_key='max_users',
            limit_value=10,
        )
        prc = PackageVersionPricing(
            package_version_id=package_version.id,
            billing_type='monthly',
            price=500,
            setup_fee=100,
            currency='SAR',
        )
        _db.session.add_all([ent, lim, prc])
        _db.session.commit()

        _db.session.refresh(package_version)
        assert len(package_version.entitlements) == 1
        assert package_version.limits[0].limit_value == 10
        assert float(package_version.pricing[0].price) == 500


class TestSubscriptionLine:
    def test_create_base_subscription_line(self, saas_tenant, package_version):
        sl = SubscriptionLine(
            tenant_id=saas_tenant.id,
            package_version_id=package_version.id,
            line_type='base',
            status='active',
            billing_type='monthly',
            quantity=1,
            unit_price=500,
            effective_from=datetime.now(timezone.utc),
            effective_to=datetime.now(timezone.utc) + timedelta(days=30),
        )
        _db.session.add(sl)
        _db.session.commit()
        assert sl.id is not None

    def test_base_subscription_overlap_exclusion(self, saas_tenant, package_version):
        now = datetime.now(timezone.utc)
        sl1 = SubscriptionLine(
            tenant_id=saas_tenant.id,
            package_version_id=package_version.id,
            line_type='base',
            status='active',
            billing_type='monthly',
            quantity=1,
            unit_price=500,
            effective_from=now,
            effective_to=now + timedelta(days=30),
        )
        _db.session.add(sl1)
        _db.session.commit()

        sl2 = SubscriptionLine(
            tenant_id=saas_tenant.id,
            package_version_id=package_version.id,
            line_type='base',
            status='active',
            billing_type='monthly',
            quantity=1,
            unit_price=500,
            effective_from=now + timedelta(days=5),
            effective_to=now + timedelta(days=35),
        )
        _db.session.add(sl2)
        with pytest.raises(IntegrityError):
            _db.session.commit()
        _db.session.rollback()

    def test_addon_can_overlap(self, saas_tenant, package_version):
        now = datetime.now(timezone.utc)
        sl1 = SubscriptionLine(
            tenant_id=saas_tenant.id,
            package_version_id=package_version.id,
            line_type='addon',
            status='active',
            billing_type='monthly',
            quantity=1,
            unit_price=100,
            effective_from=now,
            effective_to=now + timedelta(days=30),
        )
        _db.session.add(sl1)
        _db.session.commit()

        sl2 = SubscriptionLine(
            tenant_id=saas_tenant.id,
            package_version_id=package_version.id,
            line_type='addon',
            status='active',
            billing_type='monthly',
            quantity=1,
            unit_price=100,
            effective_from=now + timedelta(days=5),
            effective_to=now + timedelta(days=35),
        )
        _db.session.add(sl2)
        _db.session.commit()
        assert sl2.id is not None


class TestEntitlementGrant:
    def test_single_source_check_enforced(self, saas_tenant, saas_user):
        eg = EntitlementGrant(
            tenant_id=saas_tenant.id,
            capability_key='lab.order',
            subscription_line_id=None,
            tenant_override_id=None,
            tenant_feature_flag_id=None,
            enterprise_contract_entitlement_id=None,
            effective_from=datetime.now(timezone.utc),
        )
        _db.session.add(eg)
        with pytest.raises(IntegrityError):
            _db.session.commit()
        _db.session.rollback()

    def test_entitlement_grant_from_subscription_line(self, saas_tenant, package_version, saas_user):
        sl = SubscriptionLine(
            tenant_id=saas_tenant.id,
            package_version_id=package_version.id,
            line_type='base',
            status='active',
            billing_type='monthly',
            quantity=1,
            unit_price=500,
            effective_from=datetime.now(timezone.utc),
            effective_to=datetime.now(timezone.utc) + timedelta(days=30),
        )
        _db.session.add(sl)
        _db.session.commit()

        eg = EntitlementGrant(
            tenant_id=saas_tenant.id,
            capability_key='lab.order',
            subscription_line_id=sl.id,
            effective_from=datetime.now(timezone.utc),
            granted_by_user_id=saas_user.id,
        )
        _db.session.add(eg)
        _db.session.commit()
        assert eg.id is not None


class TestTenantEntitlement:
    def test_materialized_projection(self, saas_tenant):
        te = TenantEntitlement(
            tenant_id=saas_tenant.id,
            capability_key='lab.order',
            module_name='lab',
            effective_from=datetime.now(timezone.utc),
            is_effective=True,
            source_summary='test projection',
            calculated_at=datetime.now(timezone.utc),
            calculation_version=1,
        )
        _db.session.add(te)
        _db.session.commit()

        fetched = TenantEntitlement.query.get((saas_tenant.id, 'lab.order'))
        assert fetched is not None
        assert fetched.is_effective is True


class TestEnterpriseContract:
    def test_contract_with_entitlement(self, saas_tenant, saas_user):
        contract = EnterpriseContract(
            tenant_id=saas_tenant.id,
            contract_ref='ENT-2026-001',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365),
            signed_by='CEO',
        )
        _db.session.add(contract)
        _db.session.flush()

        ent = EnterpriseContractEntitlement(
            enterprise_contract_id=contract.id,
            capability_key='ai_imaging.analyze',
            effective_from=datetime.now(timezone.utc),
        )
        _db.session.add(ent)
        _db.session.commit()

        eg = EntitlementGrant(
            tenant_id=saas_tenant.id,
            capability_key='ai_imaging.analyze',
            enterprise_contract_entitlement_id=ent.id,
            effective_from=datetime.now(timezone.utc),
            granted_by_user_id=saas_user.id,
        )
        _db.session.add(eg)
        _db.session.commit()
        assert eg.enterprise_contract_entitlement_id == ent.id


class TestTenantOverride:
    def test_override_grant(self, saas_tenant, saas_user):
        ov = TenantOverride(
            tenant_id=saas_tenant.id,
            module_name='lab',
            capability_key='lab.advanced_report',
            override_type='grant',
            reason='Enterprise negotiation',
            granted_by=saas_user.id,
            effective_from=datetime.now(timezone.utc),
        )
        _db.session.add(ov)
        _db.session.commit()

        eg = EntitlementGrant(
            tenant_id=saas_tenant.id,
            capability_key='lab.advanced_report',
            tenant_override_id=ov.id,
            effective_from=datetime.now(timezone.utc),
            granted_by_user_id=saas_user.id,
        )
        _db.session.add(eg)
        _db.session.commit()
        assert eg.tenant_override_id == ov.id
