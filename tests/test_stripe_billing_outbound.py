"""Outbound Stripe billing SDK integration tests."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.core.saas.resolver import EntitlementResolver
from app.core.saas.lifecycle import TenantProvisioningService
from app.core.tenant.models import TenantStatus
from services.stripe_billing_service import StripeBillingError, StripeBillingService
from tests.test_saas_tenant_lifecycle import _make_package_version


@pytest.fixture
def stripe_api_key(monkeypatch):
    monkeypatch.setenv('STRIPE_SECRET_KEY', 'sk_test_outbound')
    return 'sk_test_outbound'


@pytest.fixture
def billing_tenant(app):
    version = _make_package_version([('lab', 'lab.order')])
    tenant = TenantProvisioningService.provision_tenant(
        slug=f'out-{uuid.uuid4().hex[:8]}',
        name='Outbound Billing Tenant',
        contact_email='outbound@test.local',
        package_version_id=version.id,
        billing_type='monthly',
    )
    return tenant, version


class TestStripeBillingOutbound:
    def test_ensure_customer_creates_stripe_customer(self, app, stripe_api_key, billing_tenant, monkeypatch):
        tenant, _version = billing_tenant
        mock_customer = MagicMock(id='cus_test_123')
        monkeypatch.setattr('services.stripe_billing_service.stripe.Customer.create', lambda **kw: mock_customer)

        customer_id = StripeBillingService.ensure_customer(tenant.id)
        assert customer_id == 'cus_test_123'

    def test_create_checkout_session_returns_url(self, app, stripe_api_key, billing_tenant, monkeypatch):
        tenant, version = billing_tenant
        mock_session = MagicMock(id='cs_test', url='https://checkout.stripe.test/session')
        monkeypatch.setattr(
            'services.stripe_billing_service.stripe.Customer.create',
            lambda **kw: MagicMock(id='cus_existing'),
        )
        tenant.settings = {'stripe_customer_id': 'cus_existing'}
        from app.extensions import db
        db.session.commit()

        monkeypatch.setattr(
            'services.stripe_billing_service.stripe.checkout.Session.create',
            lambda **kw: mock_session,
        )

        result = StripeBillingService.create_checkout_session(
            tenant.id,
            version.id,
            'monthly',
            success_url='https://example.com/success',
            cancel_url='https://example.com/cancel',
        )
        assert result['checkout_session_id'] == 'cs_test'
        assert 'checkout.stripe.test' in result['url']

    def test_cancel_subscription_updates_local_entitlements(self, app, stripe_api_key, billing_tenant, monkeypatch):
        tenant, _version = billing_tenant
        tenant.settings = {'stripe_subscription_id': 'sub_test_cancel'}
        from app.extensions import db
        db.session.commit()

        mock_sub = MagicMock(id='sub_test_cancel', status='canceled', cancel_at_period_end=True)
        monkeypatch.setattr(
            'services.stripe_billing_service.stripe.Subscription.modify',
            lambda *a, **k: mock_sub,
        )

        result = StripeBillingService.cancel_subscription(tenant.id, at_period_end=True)
        assert result['subscription_id'] == 'sub_test_cancel'
        db.session.refresh(tenant)
        assert tenant.status == TenantStatus.CANCELLED
        assert EntitlementResolver.is_entitled(tenant.id, 'lab.order') is False

    def test_change_plan_upgrade_refreshes_entitlements(self, app, stripe_api_key, billing_tenant, monkeypatch):
        tenant, old_version = billing_tenant
        new_version = _make_package_version([('lab', 'lab.order'), ('radiology', 'radiology.order')])
        tenant.settings = {'stripe_subscription_id': 'sub_change'}
        from app.extensions import db
        db.session.commit()

        mock_sub = {'items': {'data': [{'id': 'si_test'}]}}
        monkeypatch.setattr(
            'services.stripe_billing_service.stripe.Subscription.retrieve',
            lambda sub_id: mock_sub,
        )
        monkeypatch.setattr(
            'services.stripe_billing_service.stripe.Subscription.modify',
            lambda *a, **k: MagicMock(id='sub_change'),
        )

        result = StripeBillingService.change_plan(tenant.id, new_version.id, 'monthly')
        assert result['action'] in ('upgrade', 'downgrade')
        assert EntitlementResolver.is_entitled(tenant.id, 'lab.order') is True

    def test_missing_secret_raises(self, app, monkeypatch):
        monkeypatch.delenv('STRIPE_SECRET_KEY', raising=False)
        with pytest.raises(StripeBillingError):
            StripeBillingService.ensure_customer(1)
