"""Tests for S0-005: Tenant provisioning lifecycle with subscription lines."""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from dateutil.relativedelta import relativedelta

from app.extensions import db
from app.core.saas.lifecycle import TenantProvisioningService, ProvisioningError
from app.core.saas.resolver import EntitlementResolver
from app.core.saas.models import (
    Package,
    PackageVersion,
    PackageVersionEntitlement,
    PackageVersionPricing,
    SubscriptionLine,
    SubscriptionLineStatus,
    TenantEntitlement,
)
from app.core.module.models import TenantModule
from app.core.tenant.models import Tenant, TenantStatus, TenantSubscriptionHistory


def _make_package_version(capabilities, billing_type="monthly", price=500, trial_days=0, grace_days=0):
    pkg = Package(
        name=f"Pkg {uuid.uuid4().hex[:6]}",
        slug=f"pkg-{uuid.uuid4().hex[:8]}",
        category="bundle",
        is_active=True,
    )
    db.session.add(pkg)
    db.session.flush()

    version = PackageVersion(
        package_id=pkg.id,
        version="1.0.0",
        trial_days=trial_days,
        grace_days=grace_days,
        published_at=datetime.now(timezone.utc),
    )
    db.session.add(version)
    db.session.flush()

    pricing = PackageVersionPricing(
        package_version_id=version.id,
        billing_type=billing_type,
        price=price,
        setup_fee=0,
        currency="SAR",
    )
    db.session.add(pricing)

    for module_name, capability_key in capabilities:
        ent = PackageVersionEntitlement(
            package_version_id=version.id,
            module_name=module_name,
            capability_key=capability_key,
        )
        db.session.add(ent)

    db.session.commit()
    return version


class TestProvisionTenant:
    def test_provision_creates_tenant_line_projection_and_modules(self):
        version = _make_package_version(
            [("lab", "lab.order"), ("lab", "lab.result_entry")]
        )
        tenant = TenantProvisioningService.provision_tenant(
            slug=f"prov-{uuid.uuid4().hex[:8]}",
            name="Provisioned Tenant",
            contact_email="prov@test.local",
            package_version_id=version.id,
            billing_type="monthly",
        )

        assert tenant.id is not None
        assert tenant.status == TenantStatus.ACTIVE

        lines = SubscriptionLine.query.filter_by(tenant_id=tenant.id).all()
        assert len(lines) == 1
        assert lines[0].status == SubscriptionLineStatus.ACTIVE
        assert lines[0].line_type == "base"

        projection = TenantEntitlement.query.filter_by(tenant_id=tenant.id).all()
        assert {p.capability_key for p in projection} == {"lab.order", "lab.result_entry"}

        modules = TenantModule.query.filter_by(tenant_id=tenant.id).all()
        assert any(m.module_name == "lab" and m.is_active for m in modules)

        assert EntitlementResolver.is_entitled(tenant.id, "lab.order") is True

    def test_provision_with_trial_sets_trial_status_and_trial_end(self):
        version = _make_package_version(
            [("doctor", "clinical_encounter")],
            trial_days=14,
        )
        tenant = TenantProvisioningService.provision_tenant(
            slug=f"trial-{uuid.uuid4().hex[:8]}",
            name="Trial Tenant",
            contact_email="trial@test.local",
            package_version_id=version.id,
            billing_type="monthly",
        )

        assert tenant.status == TenantStatus.TRIAL
        line = SubscriptionLine.query.filter_by(tenant_id=tenant.id).first()
        assert line.trial_end is not None
        assert line.trial_end <= (date.today() + timedelta(days=14))

    def test_duplicate_slug_raises(self):
        version = _make_package_version([("doctor", "clinical_encounter")])
        slug = f"dup-{uuid.uuid4().hex[:8]}"
        TenantProvisioningService.provision_tenant(
            slug=slug,
            name="First",
            contact_email="first@test.local",
            package_version_id=version.id,
            billing_type="monthly",
        )

        with pytest.raises(ProvisioningError):
            TenantProvisioningService.provision_tenant(
                slug=slug,
                name="Second",
                contact_email="second@test.local",
                package_version_id=version.id,
                billing_type="monthly",
            )


class TestUpgradeAndAddons:
    def test_upgrade_ends_old_line_and_updates_projection(self):
        v1 = _make_package_version([("lab", "lab.order")])
        tenant = TenantProvisioningService.provision_tenant(
            slug=f"upg-{uuid.uuid4().hex[:8]}",
            name="Upgrade Tenant",
            contact_email="upg@test.local",
            package_version_id=v1.id,
            billing_type="monthly",
        )

        v2 = _make_package_version(
            [("lab", "lab.order"), ("radiology", "radiology.order")]
        )
        TenantProvisioningService.upgrade_tenant(
            tenant.id,
            new_package_version_id=v2.id,
            billing_type="yearly",
        )

        lines = SubscriptionLine.query.filter_by(tenant_id=tenant.id).order_by(SubscriptionLine.created_at).all()
        assert len(lines) == 2
        assert lines[0].status == SubscriptionLineStatus.ENDED
        assert lines[1].status == SubscriptionLineStatus.ACTIVE
        assert lines[1].billing_type == "yearly"

        projection = TenantEntitlement.query.filter_by(tenant_id=tenant.id).all()
        assert {p.capability_key for p in projection} == {"lab.order", "radiology.order"}

        history = TenantSubscriptionHistory.query.filter_by(tenant_id=tenant.id, action="UPGRADE").first()
        assert history is not None

    def test_addon_adds_capability_without_ending_base(self):
        base = _make_package_version([("doctor", "clinical_encounter")])
        tenant = TenantProvisioningService.provision_tenant(
            slug=f"addon-{uuid.uuid4().hex[:8]}",
            name="Addon Tenant",
            contact_email="addon@test.local",
            package_version_id=base.id,
            billing_type="monthly",
        )

        addon = _make_package_version([("ai_imaging", "ai_analysis")])
        TenantProvisioningService.add_addon(
            tenant.id,
            package_version_id=addon.id,
            billing_type="monthly",
        )

        active_lines = SubscriptionLine.query.filter_by(
            tenant_id=tenant.id, status=SubscriptionLineStatus.ACTIVE
        ).all()
        assert len(active_lines) == 2

        projection = TenantEntitlement.query.filter_by(tenant_id=tenant.id).all()
        assert {p.capability_key for p in projection} == {"clinical_encounter", "ai_analysis"}


class TestRenewSuspendReactivateCancel:
    def test_renew_extends_line_and_grants(self):
        version = _make_package_version([("lab", "lab.order")])
        tenant = TenantProvisioningService.provision_tenant(
            slug=f"renew-{uuid.uuid4().hex[:8]}",
            name="Renew Tenant",
            contact_email="renew@test.local",
            package_version_id=version.id,
            billing_type="monthly",
        )
        line = SubscriptionLine.query.filter_by(tenant_id=tenant.id).first()
        original_effective_to = line.effective_to

        TenantProvisioningService.renew_base_line(line.id, periods=1)

        line = SubscriptionLine.query.get(line.id)
        assert line.effective_to > original_effective_to
        assert EntitlementResolver.is_entitled(tenant.id, "lab.order") is True

    def test_suspend_denies_entitlement_reactivate_restores(self):
        version = _make_package_version([("lab", "lab.order")])
        tenant = TenantProvisioningService.provision_tenant(
            slug=f"sus-{uuid.uuid4().hex[:8]}",
            name="Suspend Tenant",
            contact_email="sus@test.local",
            package_version_id=version.id,
            billing_type="monthly",
        )
        assert EntitlementResolver.is_entitled(tenant.id, "lab.order") is True

        TenantProvisioningService.suspend_tenant(tenant.id, "late payment")
        assert EntitlementResolver.is_entitled(tenant.id, "lab.order") is False

        TenantProvisioningService.reactivate_tenant(tenant.id)
        assert EntitlementResolver.is_entitled(tenant.id, "lab.order") is True

    def test_cancel_ends_lines_and_removes_entitlements(self):
        version = _make_package_version([("lab", "lab.order")])
        tenant = TenantProvisioningService.provision_tenant(
            slug=f"cancel-{uuid.uuid4().hex[:8]}",
            name="Cancel Tenant",
            contact_email="cancel@test.local",
            package_version_id=version.id,
            billing_type="monthly",
        )
        TenantProvisioningService.cancel_tenant(tenant.id)

        assert tenant.status == TenantStatus.CANCELLED
        lines = SubscriptionLine.query.filter_by(tenant_id=tenant.id).all()
        assert all(line.status == SubscriptionLineStatus.ENDED for line in lines)

        projection = TenantEntitlement.query.filter_by(tenant_id=tenant.id).all()
        assert len(projection) == 0
        assert EntitlementResolver.is_entitled(tenant.id, "lab.order") is False
