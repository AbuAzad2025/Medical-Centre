"""Stripe webhook → entitlement lifecycle tests."""

import hashlib
import hmac
import json
import os
import time
import uuid

import pytest

from app.extensions import db
from app.core.saas.resolver import EntitlementResolver
from app.core.saas.lifecycle import TenantProvisioningService
from app.core.tenant.models import Tenant, TenantStatus
from services.stripe_subscription_service import StripeSubscriptionService, StripeWebhookError
from tests.test_saas_tenant_lifecycle import _make_package_version


def _sign(payload: bytes, secret: str) -> str:
    ts = str(int(time.time()))
    signed = f'{ts}.{payload.decode("utf-8")}'.encode('utf-8')
    digest = hmac.new(secret.encode('utf-8'), signed, hashlib.sha256).hexdigest()
    return f't={ts},v1={digest}'


@pytest.fixture
def stripe_secret(monkeypatch):
    secret = 'whsec_test_secret'
    monkeypatch.setenv('STRIPE_WEBHOOK_SECRET', secret)
    return secret


@pytest.fixture
def billed_tenant(app):
    version = _make_package_version([('lab', 'lab.order')])
    tenant = TenantProvisioningService.provision_tenant(
        slug=f'bill-{uuid.uuid4().hex[:8]}',
        name='Billing Tenant',
        contact_email='bill@test.local',
        package_version_id=version.id,
        billing_type='monthly',
    )
    return tenant


class TestStripeWebhookSecurity:
    def test_rejects_missing_signature(self, stripe_secret):
        with pytest.raises(StripeWebhookError):
            StripeSubscriptionService.ingest_webhook(b'{}', '')


class TestStripeWebhookLifecycle:
    def test_payment_failed_suspends_and_blocks_entitlement(self, stripe_secret, billed_tenant):
        payload = json.dumps({
            'type': 'invoice.payment_failed',
            'data': {'object': {'metadata': {'tenant_id': str(billed_tenant.id)}}},
        }).encode('utf-8')
        sig = _sign(payload, stripe_secret)
        result = StripeSubscriptionService.ingest_webhook(payload, sig)
        assert result['action'] == 'payment_failed'
        db.session.refresh(billed_tenant)
        assert billed_tenant.status == TenantStatus.SUSPENDED
        assert EntitlementResolver.is_entitled(billed_tenant.id, 'lab.order') is False

    def test_invoice_paid_reactivates_entitlement(self, stripe_secret, billed_tenant):
        TenantProvisioningService.suspend_tenant(billed_tenant.id, 'test')
        payload = json.dumps({
            'type': 'invoice.paid',
            'data': {'object': {'metadata': {'tenant_id': str(billed_tenant.id)}}},
        }).encode('utf-8')
        sig = _sign(payload, stripe_secret)
        StripeSubscriptionService.ingest_webhook(payload, sig)
        db.session.refresh(billed_tenant)
        assert billed_tenant.status == TenantStatus.ACTIVE
        assert EntitlementResolver.is_entitled(billed_tenant.id, 'lab.order') is True
