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
from app.core.saas.models import StripeWebhookEvent, StripeWebhookEventStatus
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
    def test_payment_failed_suspends_and_blocks_entitlement(self, app, stripe_secret, billed_tenant, monkeypatch):
        event_id = f'evt_{uuid.uuid4().hex}'
        payload = json.dumps({
            'id': event_id,
            'type': 'invoice.payment_failed',
            'data': {'object': {'metadata': {'tenant_id': str(billed_tenant.id)}}},
        }).encode('utf-8')
        sig = _sign(payload, stripe_secret)
        monkeypatch.setattr(
            'services.stripe_subscription_service.stripe.Webhook.construct_event',
            lambda p, s, sec: json.loads(p),
        )
        result = StripeSubscriptionService.ingest_webhook(payload, sig)
        assert result['action'] == 'payment_failed'
        db.session.refresh(billed_tenant)
        assert billed_tenant.status == TenantStatus.SUSPENDED
        assert EntitlementResolver.is_entitled(billed_tenant.id, 'lab.order') is False

    def test_invoice_paid_reactivates_entitlement(self, app, stripe_secret, billed_tenant, monkeypatch):
        TenantProvisioningService.suspend_tenant(billed_tenant.id, 'test')
        event_id = f'evt_{uuid.uuid4().hex}'
        payload = json.dumps({
            'id': event_id,
            'type': 'invoice.paid',
            'data': {'object': {'metadata': {'tenant_id': str(billed_tenant.id)}}},
        }).encode('utf-8')
        sig = _sign(payload, stripe_secret)
        monkeypatch.setattr(
            'services.stripe_subscription_service.stripe.Webhook.construct_event',
            lambda p, s, sec: json.loads(p),
        )
        StripeSubscriptionService.ingest_webhook(payload, sig)
        db.session.refresh(billed_tenant)
        assert billed_tenant.status == TenantStatus.ACTIVE
        assert EntitlementResolver.is_entitled(billed_tenant.id, 'lab.order') is True


class TestStripeWebhookIdempotency:
    def test_duplicate_event_returns_already_processed(self, app, stripe_secret, billed_tenant, monkeypatch):
        """Second POST with same event_id returns 200 without double state change."""
        event_id = f'evt_{uuid.uuid4().hex}'
        payload = json.dumps({
            'id': event_id,
            'type': 'invoice.payment_failed',
            'data': {'object': {'metadata': {'tenant_id': str(billed_tenant.id)}}},
        }).encode('utf-8')
        sig = _sign(payload, stripe_secret)
        monkeypatch.setattr(
            'services.stripe_subscription_service.stripe.Webhook.construct_event',
            lambda p, s, sec: json.loads(p),
        )

        result1 = StripeSubscriptionService.ingest_webhook(payload, sig)
        assert result1['action'] == 'payment_failed'

        record = db.session.get(StripeWebhookEvent, event_id)
        assert record is not None
        assert record.status == StripeWebhookEventStatus.PROCESSED

        TenantProvisioningService.reactivate_tenant(billed_tenant.id)
        db.session.commit()
        db.session.refresh(billed_tenant)
        assert billed_tenant.status == TenantStatus.ACTIVE

        result2 = StripeSubscriptionService.ingest_webhook(payload, sig)
        assert result2['already_processed'] is True
        assert result2['event_id'] == event_id

        db.session.refresh(billed_tenant)
        assert billed_tenant.status == TenantStatus.ACTIVE
