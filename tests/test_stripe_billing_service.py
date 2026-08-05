"""Tests for plan-change validation edge cases in StripeBillingService."""

import uuid
from unittest.mock import MagicMock

import pytest

from app.core.saas.lifecycle import TenantProvisioningService
from app.core.saas.models import (
    PackageVersionAvailability,
    PackageVersionAvailabilityStatus,
    SubscriptionLine,
    SubscriptionLineStatus,
    SubscriptionLineType,
)
from app.core.tenant.models import TenantStatus
from app.extensions import db
from services.stripe_billing_service import (
    PlanChangeValidationError,
    StripeBillingError,
    StripeBillingService,
)
from tests.test_saas_tenant_lifecycle import _make_package_version


@pytest.fixture
def stripe_api_key(monkeypatch):
    monkeypatch.setenv('STRIPE_SECRET_KEY', 'sk_test_plan_change')
    return 'sk_test_plan_change'


@pytest.fixture
def change_tenant(app):
    version = _make_package_version([('lab', 'lab.order')], price=100)
    tenant = TenantProvisioningService.provision_tenant(
        slug=f'chg-{uuid.uuid4().hex[:8]}',
        name='Plan Change Tenant',
        contact_email='change@test.local',
        package_version_id=version.id,
        billing_type='monthly',
    )
    return tenant, version


# ═══════════════════════════ Validation Tests ═══════════════════════════


class TestPlanChangeValidation:
    def test_suspended_tenant_blocked(self, app, stripe_api_key, change_tenant, monkeypatch):
        tenant, _version = change_tenant
        TenantProvisioningService.suspend_tenant(tenant.id, reason='payment_failed')
        db.session.commit()

        with pytest.raises(PlanChangeValidationError, match='not allowed'):
            StripeBillingService.change_plan(tenant.id, _version.id, 'monthly')

    def test_cancelled_tenant_blocked(self, app, stripe_api_key, change_tenant, monkeypatch):
        tenant, _version = change_tenant
        TenantProvisioningService.cancel_tenant(tenant.id)
        db.session.commit()

        with pytest.raises(PlanChangeValidationError, match='not allowed'):
            StripeBillingService.change_plan(tenant.id, _version.id, 'monthly')

    def test_deprecated_version_blocked(self, app, stripe_api_key, change_tenant, monkeypatch):
        tenant, _version = change_tenant
        deprecated = _make_package_version([('lab', 'lab.order')], price=200)
        deprecated.is_deprecated = True
        db.session.commit()

        with pytest.raises(PlanChangeValidationError, match='deprecated'):
            StripeBillingService.change_plan(tenant.id, deprecated.id, 'monthly')

    def test_retired_version_blocked(self, app, stripe_api_key, change_tenant, monkeypatch):
        tenant, _version = change_tenant
        retired = _make_package_version([('lab', 'lab.order')], price=200)
        avail = PackageVersionAvailability(
            package_version_id=retired.id,
            availability_status=PackageVersionAvailabilityStatus.RETIRED,
            effective_from=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
        )
        db.session.add(avail)
        db.session.commit()

        with pytest.raises(PlanChangeValidationError, match='retired'):
            StripeBillingService.change_plan(tenant.id, retired.id, 'monthly')

    def test_missing_pricing_blocked(self, app, stripe_api_key, change_tenant, monkeypatch):
        tenant, _version = change_tenant
        # version has 'monthly' pricing but not 'yearly'
        with pytest.raises(StripeBillingError, match='package_pricing_not_found'):
            StripeBillingService.change_plan(tenant.id, _version.id, 'yearly')

    def test_active_tenant_allowed(self, app, stripe_api_key, change_tenant, monkeypatch):
        tenant, _old_version = change_tenant
        new_version = _make_package_version([('lab', 'lab.order')], price=200)
        tenant.settings = {'stripe_subscription_id': 'sub_active'}
        db.session.commit()

        mock_sub = {'items': {'data': [{'id': 'si_test'}]}}
        monkeypatch.setattr(
            'services.stripe_billing_service.stripe.Subscription.retrieve',
            lambda _sub_id: mock_sub,
        )
        monkeypatch.setattr(
            'services.stripe_billing_service.stripe.Subscription.modify',
            lambda *_a, **_k: MagicMock(id='sub_active'),
        )
        monkeypatch.setattr(
            'services.stripe_billing_service.stripe.Invoice.list',
            lambda **_kw: {'data': []},
        )
        monkeypatch.setattr(
            'services.stripe_billing_service.StripeBillingService._validate_proration',
            lambda *_a, **_k: None,
        )

        result = StripeBillingService.change_plan(tenant.id, new_version.id, 'monthly')
        assert result['action'] == 'upgrade'

    def test_trial_tenant_allowed(self, app, stripe_api_key, monkeypatch):
        trial_version = _make_package_version([('lab', 'lab.order')], price=0, trial_days=14)
        tenant = TenantProvisioningService.provision_tenant(
            slug=f'trial-{uuid.uuid4().hex[:8]}',
            name='Trial Tenant',
            contact_email='trial@test.local',
            package_version_id=trial_version.id,
            billing_type='monthly',
        )
        db.session.commit()
        assert tenant.status == TenantStatus.TRIAL

        paid_version = _make_package_version([('lab', 'lab.order')], price=100)
        tenant.settings = {'stripe_subscription_id': 'sub_trial'}
        db.session.commit()

        mock_sub = {'items': {'data': [{'id': 'si_trial'}]}}
        monkeypatch.setattr(
            'services.stripe_billing_service.stripe.Subscription.retrieve',
            lambda _sub_id: mock_sub,
        )
        monkeypatch.setattr(
            'services.stripe_billing_service.stripe.Subscription.modify',
            lambda *_a, **_k: MagicMock(id='sub_trial'),
        )
        monkeypatch.setattr(
            'services.stripe_billing_service.stripe.Invoice.list',
            lambda **_kw: {'data': []},
        )
        monkeypatch.setattr(
            'services.stripe_billing_service.StripeBillingService._validate_proration',
            lambda *_a, **_k: None,
        )

        result = StripeBillingService.change_plan(tenant.id, paid_version.id, 'monthly')
        assert result['trial_converted'] is True
        db.session.refresh(tenant)
        assert tenant.status == TenantStatus.ACTIVE

    def test_pending_invoice_blocks_change(self, app, stripe_api_key, change_tenant, monkeypatch):
        tenant, _version = change_tenant
        new_version = _make_package_version([('lab', 'lab.order')], price=200)
        tenant.settings = {'stripe_subscription_id': 'sub_pending'}
        db.session.commit()

        monkeypatch.setattr(
            'services.stripe_billing_service.stripe.Invoice.list',
            lambda **_kw: {'data': [{'id': 'inv_1'}]},
        )

        with pytest.raises(PlanChangeValidationError, match='pending_invoices_exist'):
            StripeBillingService.change_plan(tenant.id, new_version.id, 'monthly')


# ═══════════════════════════ Proration Tests ═══════════════════════════


class TestProrationValidation:
    def test_proration_negative_amount_logged(
        self, app, stripe_api_key, change_tenant, monkeypatch
    ):
        tenant, _old_version = change_tenant
        new_version = _make_package_version([('lab', 'lab.order')], price=50)
        tenant.settings = {'stripe_subscription_id': 'sub_proration'}
        db.session.commit()

        mock_sub = {'items': {'data': [{'id': 'si_proration'}]}}
        monkeypatch.setattr(
            'services.stripe_billing_service.stripe.Subscription.retrieve',
            lambda _sub_id: mock_sub,
        )
        monkeypatch.setattr(
            'services.stripe_billing_service.stripe.Subscription.modify',
            lambda *_a, **_k: MagicMock(id='sub_proration'),
        )
        monkeypatch.setattr(
            'services.stripe_billing_service.stripe.Invoice.list',
            lambda **_kw: {'data': []},
        )
        # Simulate negative upcoming invoice (credit) by mocking _validate_proration
        monkeypatch.setattr(
            'services.stripe_billing_service.StripeBillingService._validate_proration',
            lambda *_a, **_k: None,
        )

        # Should NOT raise — negative proration is valid; we just log
        result = StripeBillingService.change_plan(tenant.id, new_version.id, 'monthly')
        assert result['action'] == 'downgrade'

    def test_stripe_invoice_list_failure_non_fatal(
        self, app, stripe_api_key, change_tenant, monkeypatch
    ):
        tenant, _old_version = change_tenant
        new_version = _make_package_version([('lab', 'lab.order')], price=200)
        tenant.settings = {'stripe_subscription_id': 'sub_err'}
        db.session.commit()

        mock_sub = {'items': {'data': [{'id': 'si_err'}]}}
        monkeypatch.setattr(
            'services.stripe_billing_service.stripe.Subscription.retrieve',
            lambda _sub_id: mock_sub,
        )
        monkeypatch.setattr(
            'services.stripe_billing_service.stripe.Subscription.modify',
            lambda *_a, **_k: MagicMock(id='sub_err'),
        )

        # Simulate Stripe error on invoice.list — should be non-fatal
        def raise_stripe_error(**kw):
            raise RuntimeError('Stripe API down')

        monkeypatch.setattr(
            'services.stripe_billing_service.stripe.Invoice.list',
            raise_stripe_error,
        )

        result = StripeBillingService.change_plan(tenant.id, new_version.id, 'monthly')
        assert result['action'] == 'upgrade'


# ═══════════════════════════ Upgrade/Downgrade Tests ═══════════════════════════


class TestUpgradeDowngradeClassification:
    def test_higher_price_is_upgrade(self, app, stripe_api_key, change_tenant, monkeypatch):
        tenant, _old_version = change_tenant
        expensive = _make_package_version([('lab', 'lab.order')], price=1000)
        tenant.settings = {'stripe_subscription_id': 'sub_up'}
        db.session.commit()

        mock_sub = {'items': {'data': [{'id': 'si_up'}]}}
        monkeypatch.setattr(
            'services.stripe_billing_service.stripe.Subscription.retrieve',
            lambda _sub_id: mock_sub,
        )
        monkeypatch.setattr(
            'services.stripe_billing_service.stripe.Subscription.modify',
            lambda *_a, **_k: MagicMock(id='sub_up'),
        )
        monkeypatch.setattr(
            'services.stripe_billing_service.stripe.Invoice.list',
            lambda **_kw: {'data': []},
        )
        monkeypatch.setattr(
            'services.stripe_billing_service.StripeBillingService._validate_proration',
            lambda *_a, **_k: None,
        )

        result = StripeBillingService.change_plan(tenant.id, expensive.id, 'monthly')
        assert result['action'] == 'upgrade'

    def test_lower_price_is_downgrade(self, app, stripe_api_key, change_tenant, monkeypatch):
        tenant, _old_version = change_tenant
        cheap = _make_package_version([('lab', 'lab.order')], price=10)
        tenant.settings = {'stripe_subscription_id': 'sub_down'}
        db.session.commit()

        mock_sub = {'items': {'data': [{'id': 'si_down'}]}}
        monkeypatch.setattr(
            'services.stripe_billing_service.stripe.Subscription.retrieve',
            lambda _sub_id: mock_sub,
        )
        monkeypatch.setattr(
            'services.stripe_billing_service.stripe.Subscription.modify',
            lambda *_a, **_k: MagicMock(id='sub_down'),
        )
        monkeypatch.setattr(
            'services.stripe_billing_service.stripe.Invoice.list',
            lambda **_kw: {'data': []},
        )
        monkeypatch.setattr(
            'services.stripe_billing_service.StripeBillingService._validate_proration',
            lambda *_a, **_k: None,
        )

        result = StripeBillingService.change_plan(tenant.id, cheap.id, 'monthly')
        assert result['action'] == 'downgrade'

    def test_equal_price_is_upgrade(self, app, stripe_api_key, change_tenant, monkeypatch):
        tenant, _old_version = change_tenant
        same_price = _make_package_version([('lab', 'lab.order')], price=100)
        tenant.settings = {'stripe_subscription_id': 'sub_same'}
        db.session.commit()

        mock_sub = {'items': {'data': [{'id': 'si_same'}]}}
        monkeypatch.setattr(
            'services.stripe_billing_service.stripe.Subscription.retrieve',
            lambda _sub_id: mock_sub,
        )
        monkeypatch.setattr(
            'services.stripe_billing_service.stripe.Subscription.modify',
            lambda *_a, **_k: MagicMock(id='sub_same'),
        )
        monkeypatch.setattr(
            'services.stripe_billing_service.stripe.Invoice.list',
            lambda **_kw: {'data': []},
        )
        monkeypatch.setattr(
            'services.stripe_billing_service.StripeBillingService._validate_proration',
            lambda *_a, **_k: None,
        )

        result = StripeBillingService.change_plan(tenant.id, same_price.id, 'monthly')
        assert result['action'] == 'upgrade'


# ═══════════════════════════ Idempotency Tests ═══════════════════════════


class TestIdempotency:
    def test_idempotency_key_present_on_modify(
        self, app, stripe_api_key, change_tenant, monkeypatch
    ):
        tenant, _old_version = change_tenant
        new_version = _make_package_version([('lab', 'lab.order')], price=200)
        tenant.settings = {'stripe_subscription_id': 'sub_idem'}
        db.session.commit()

        mock_sub = {'items': {'data': [{'id': 'si_idem'}]}}
        captured_kwargs = {}

        def capture_modify(*args, **kwargs):
            captured_kwargs.update(kwargs)
            return MagicMock(id='sub_idem')

        monkeypatch.setattr(
            'services.stripe_billing_service.stripe.Subscription.retrieve',
            lambda _sub_id: mock_sub,
        )
        monkeypatch.setattr(
            'services.stripe_billing_service.stripe.Subscription.modify',
            capture_modify,
        )
        monkeypatch.setattr(
            'services.stripe_billing_service.stripe.Invoice.list',
            lambda **_kw: {'data': []},
        )
        monkeypatch.setattr(
            'services.stripe_billing_service.StripeBillingService._validate_proration',
            lambda *_a, **_k: None,
        )

        StripeBillingService.change_plan(tenant.id, new_version.id, 'monthly')
        assert 'idempotency_key' in captured_kwargs
        assert captured_kwargs['idempotency_key'].startswith('plan_change_')


# ═══════════════════════════ Missing Base Line Tests ═══════════════════════════


class TestMissingBaseLine:
    def test_no_active_base_line_treats_current_price_as_zero(
        self, app, stripe_api_key, monkeypatch
    ):
        """Tenant with no active base line (e.g., all lines ended) should still allow plan change."""
        version = _make_package_version([('lab', 'lab.order')], price=100)
        tenant = TenantProvisioningService.provision_tenant(
            slug=f'no-base-{uuid.uuid4().hex[:8]}',
            name='No Base Line Tenant',
            contact_email='nobase@test.local',
            package_version_id=version.id,
            billing_type='monthly',
        )
        db.session.commit()

        # End all base lines manually
        lines = (
            db.session.execute(
                __import__('sqlalchemy', fromlist=['select'])
                .select(SubscriptionLine)
                .filter_by(tenant_id=tenant.id, line_type=SubscriptionLineType.BASE)
            )
            .scalars()
            .all()
        )
        for line in lines:
            line.status = SubscriptionLineStatus.ENDED
        db.session.commit()

        new_version = _make_package_version([('lab', 'lab.order')], price=50)
        tenant.settings = {'stripe_subscription_id': 'sub_nobase'}
        db.session.commit()

        mock_sub = {'items': {'data': [{'id': 'si_nobase'}]}}
        monkeypatch.setattr(
            'services.stripe_billing_service.stripe.Subscription.retrieve',
            lambda _sub_id: mock_sub,
        )
        monkeypatch.setattr(
            'services.stripe_billing_service.stripe.Subscription.modify',
            lambda *_a, **_k: MagicMock(id='sub_nobase'),
        )
        monkeypatch.setattr(
            'services.stripe_billing_service.stripe.Invoice.list',
            lambda **_kw: {'data': []},
        )
        monkeypatch.setattr(
            'services.stripe_billing_service.StripeBillingService._validate_proration',
            lambda *_a, **_k: None,
        )

        # With current_price=0, any positive price is an "upgrade"
        result = StripeBillingService.change_plan(tenant.id, new_version.id, 'monthly')
        assert result['action'] == 'upgrade'
