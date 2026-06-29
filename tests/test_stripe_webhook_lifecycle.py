"""Stripe subscription webhook lifecycle tests (handle_event + ingest_webhook)."""

import hashlib
import hmac
import json
import time
import uuid

import pytest

from app.extensions import db
from app.core.saas.resolver import EntitlementResolver
from app.core.saas.lifecycle import TenantProvisioningService
from app.core.saas.models import StripeWebhookEvent, StripeWebhookEventStatus
from app.core.tenant.models import TenantStatus
from services.stripe_subscription_service import StripeSubscriptionService, StripeWebhookError
from tests.test_saas_tenant_lifecycle import _make_package_version


def _sign(payload: bytes, secret: str) -> str:
    ts = str(int(time.time()))
    signed = f'{ts}.{payload.decode("utf-8")}'.encode('utf-8')
    digest = hmac.new(secret.encode('utf-8'), signed, hashlib.sha256).hexdigest()
    return f't={ts},v1={digest}'


@pytest.fixture
def stripe_secret(monkeypatch):
    secret = 'whsec_lifecycle_test'
    monkeypatch.setenv('STRIPE_WEBHOOK_SECRET', secret)
    return secret


@pytest.fixture
def billed_tenant(app):
    version = _make_package_version([('lab', 'lab.order')])
    tenant = TenantProvisioningService.provision_tenant(
        slug=f'wh-{uuid.uuid4().hex[:8]}',
        name='Webhook Lifecycle Tenant',
        contact_email='webhook@test.local',
        package_version_id=version.id,
        billing_type='monthly',
    )
    return tenant


def _event(event_type, tenant, **obj_extra):
    obj = {'metadata': {'tenant_id': str(tenant.id)}, **obj_extra}
    return {'type': event_type, 'data': {'object': obj}}


class TestStripeWebhookSubscriptionDeleted:
    def test_subscription_deleted_cancels_tenant(self, app, billed_tenant):
        event = _event('customer.subscription.deleted', billed_tenant, id='sub_deleted_test')

        result = StripeSubscriptionService.handle_event(event)

        assert result['action'] == 'subscription_deleted'
        assert result['tenant_id'] == billed_tenant.id
        db.session.refresh(billed_tenant)
        assert billed_tenant.status == TenantStatus.CANCELLED
        assert EntitlementResolver.is_entitled(billed_tenant.id, 'lab.order') is False


class TestStripeWebhookCheckoutCompleted:
    def test_checkout_session_completed_activates_tenant(self, app, billed_tenant):
        TenantProvisioningService.suspend_tenant(billed_tenant.id, 'awaiting_payment')
        event = _event(
            'checkout.session.completed',
            billed_tenant,
            customer='cus_checkout',
            subscription='sub_checkout',
        )

        result = StripeSubscriptionService.handle_event(event)

        assert result['action'] == 'checkout_completed'
        db.session.refresh(billed_tenant)
        assert billed_tenant.status == TenantStatus.ACTIVE
        assert billed_tenant.settings['stripe_customer_id'] == 'cus_checkout'
        assert billed_tenant.settings['stripe_subscription_id'] == 'sub_checkout'
        assert EntitlementResolver.is_entitled(billed_tenant.id, 'lab.order') is True

    def test_checkout_ignored_when_tenant_missing(self, app):
        event = {
            'type': 'checkout.session.completed',
            'data': {'object': {'metadata': {'tenant_id': '99999999'}}},
        }
        result = StripeSubscriptionService.handle_event(event)
        assert result['ignored'] is True
        assert result['reason'] == 'tenant_not_found'


class TestStripeWebhookSubscriptionUpdated:
    def test_past_due_suspends_tenant(self, app, billed_tenant):
        event = _event('customer.subscription.updated', billed_tenant, id='sub_pd', status='past_due')

        result = StripeSubscriptionService.handle_event(event)

        assert result['action'] == 'subscription_updated'
        assert result['stripe_status'] == 'past_due'
        db.session.refresh(billed_tenant)
        assert billed_tenant.status == TenantStatus.SUSPENDED
        assert EntitlementResolver.is_entitled(billed_tenant.id, 'lab.order') is False

    def test_unpaid_suspends_tenant(self, app, billed_tenant):
        event = _event('customer.subscription.updated', billed_tenant, id='sub_unpaid', status='unpaid')

        StripeSubscriptionService.handle_event(event)

        db.session.refresh(billed_tenant)
        assert billed_tenant.status == TenantStatus.SUSPENDED

    def test_active_reactivates_suspended_tenant(self, app, billed_tenant):
        TenantProvisioningService.suspend_tenant(billed_tenant.id, 'stripe:past_due')
        event = _event('customer.subscription.updated', billed_tenant, id='sub_active', status='active')

        result = StripeSubscriptionService.handle_event(event)

        assert result['stripe_status'] == 'active'
        db.session.refresh(billed_tenant)
        assert billed_tenant.status == TenantStatus.ACTIVE
        assert EntitlementResolver.is_entitled(billed_tenant.id, 'lab.order') is True

    def test_trialing_keeps_active(self, app, billed_tenant):
        TenantProvisioningService.suspend_tenant(billed_tenant.id, 'test')
        event = _event('customer.subscription.updated', billed_tenant, id='sub_trial', status='trialing')

        StripeSubscriptionService.handle_event(event)

        db.session.refresh(billed_tenant)
        assert billed_tenant.status == TenantStatus.ACTIVE

    def test_canceled_cancels_tenant(self, app, billed_tenant):
        event = _event('customer.subscription.updated', billed_tenant, id='sub_cancel', status='canceled')

        StripeSubscriptionService.handle_event(event)

        db.session.refresh(billed_tenant)
        assert billed_tenant.status == TenantStatus.CANCELLED


class TestStripeWebhookSubscriptionCreated:
    def test_subscription_created_stores_refs_and_activates(self, app, billed_tenant):
        TenantProvisioningService.suspend_tenant(billed_tenant.id, 'pending')
        event = _event(
            'customer.subscription.created',
            billed_tenant,
            id='sub_new',
            customer='cus_new',
            status='active',
        )

        result = StripeSubscriptionService.handle_event(event)

        assert result['action'] == 'subscription_created'
        db.session.refresh(billed_tenant)
        assert billed_tenant.status == TenantStatus.ACTIVE
        assert billed_tenant.settings['stripe_subscription_id'] == 'sub_new'


class TestStripeWebhookInvoices:
    def test_invoice_payment_failed_suspends(self, app, billed_tenant):
        event = _event('invoice.payment_failed', billed_tenant)

        result = StripeSubscriptionService.handle_event(event)

        assert result['action'] == 'payment_failed'
        db.session.refresh(billed_tenant)
        assert billed_tenant.status == TenantStatus.SUSPENDED

    def test_invoice_paid_reactivates(self, app, billed_tenant):
        TenantProvisioningService.suspend_tenant(billed_tenant.id, 'stripe:payment_failed')
        event = _event('invoice.paid', billed_tenant)

        result = StripeSubscriptionService.handle_event(event)

        assert result['action'] == 'invoice_paid'
        db.session.refresh(billed_tenant)
        assert billed_tenant.status == TenantStatus.ACTIVE
        assert EntitlementResolver.is_entitled(billed_tenant.id, 'lab.order') is True


class TestStripeWebhookTenantResolution:
    def test_resolves_tenant_by_stripe_customer_id(self, app, billed_tenant):
        customer_id = f'cus_{uuid.uuid4().hex[:12]}'
        billed_tenant.settings = {**(billed_tenant.settings or {}), 'stripe_customer_id': customer_id}
        db.session.commit()

        event = {
            'type': 'invoice.payment_failed',
            'data': {'object': {'customer': customer_id}},
        }
        result = StripeSubscriptionService.handle_event(event)

        assert result['action'] == 'payment_failed'
        assert result['tenant_id'] == billed_tenant.id
        db.session.refresh(billed_tenant)
        assert billed_tenant.status == TenantStatus.SUSPENDED


class TestStripeWebhookUnsupported:
    def test_unknown_event_type_ignored(self, app, billed_tenant):
        event = _event('charge.refunded', billed_tenant)
        result = StripeSubscriptionService.handle_event(event)
        assert result['ignored'] is True
        assert result['reason'] == 'unsupported_event'


class TestStripeWebhookIngestIdempotency:
    def test_duplicate_event_returns_already_processed(self, app, stripe_secret, billed_tenant, monkeypatch):
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
        assert record.status == StripeWebhookEventStatus.PROCESSED

        TenantProvisioningService.reactivate_tenant(billed_tenant.id)
        db.session.commit()

        result2 = StripeSubscriptionService.ingest_webhook(payload, sig)
        assert result2['already_processed'] is True
        db.session.refresh(billed_tenant)
        assert billed_tenant.status == TenantStatus.ACTIVE

    def test_missing_event_id_raises(self, app, stripe_secret, monkeypatch):
        payload = json.dumps({'type': 'invoice.paid', 'data': {'object': {}}}).encode()
        monkeypatch.setattr(
            'services.stripe_subscription_service.stripe.Webhook.construct_event',
            lambda p, s, sec: json.loads(p),
        )
        with pytest.raises(StripeWebhookError, match='missing_event_id'):
            StripeSubscriptionService.ingest_webhook(payload, _sign(payload, stripe_secret))

    def test_webhook_secret_not_configured(self, app, monkeypatch):
        monkeypatch.delenv('STRIPE_WEBHOOK_SECRET', raising=False)
        with pytest.raises(StripeWebhookError, match='stripe_webhook_not_configured'):
            StripeSubscriptionService.webhook_secret()

    def test_tenant_not_found_paths_return_ignored(self, app):
        missing = {'type': 'customer.subscription.updated', 'data': {'object': {'metadata': {'tenant_id': '99999999'}}}}
        result = StripeSubscriptionService.handle_event(missing)
        assert result['reason'] == 'tenant_not_found'

    def test_invoice_paid_renew_base_line(self, app, billed_tenant, monkeypatch):
        TenantProvisioningService.suspend_tenant(billed_tenant.id, 'test')
        from app.core.saas.models import SubscriptionLine, SubscriptionLineStatus, SubscriptionLineType
        line = SubscriptionLine.query.filter_by(
            tenant_id=billed_tenant.id,
            line_type=SubscriptionLineType.BASE,
            status=SubscriptionLineStatus.ACTIVE,
        ).first()
        billed_tenant.settings = {**(billed_tenant.settings or {}), 'stripe_base_line_id': str(line.id)}
        db.session.commit()

        called = []
        monkeypatch.setattr(
            TenantProvisioningService,
            'renew_base_line',
            lambda line_id: called.append(line_id),
        )
        event = _event('invoice.paid', billed_tenant)
        StripeSubscriptionService.handle_event(event)
        assert called == [line.id]


class TestStripeWebhookIngestFailures:
    def test_invalid_event_payload_raises(self, app, stripe_secret, monkeypatch):
        monkeypatch.setattr(
            'services.stripe_subscription_service.stripe.Webhook.construct_event',
            lambda p, s, sec: ['not', 'a', 'dict'],
        )
        payload = b'[]'
        with pytest.raises(StripeWebhookError, match='invalid_event_payload'):
            StripeSubscriptionService.ingest_webhook(payload, _sign(payload, stripe_secret))

    def test_ingest_marks_failed_on_handler_error(self, app, stripe_secret, billed_tenant, monkeypatch):
        event_id = f'evt_{uuid.uuid4().hex}'
        payload = json.dumps({
            'id': event_id,
            'type': 'invoice.paid',
            'data': {'object': {'metadata': {'tenant_id': str(billed_tenant.id)}}},
        }).encode('utf-8')
        monkeypatch.setattr(
            'services.stripe_subscription_service.stripe.Webhook.construct_event',
            lambda p, s, sec: json.loads(p),
        )
        monkeypatch.setattr(
            StripeSubscriptionService,
            'handle_event',
            lambda event: (_ for _ in ()).throw(RuntimeError('handler boom')),
        )
        with pytest.raises(RuntimeError, match='handler boom'):
            StripeSubscriptionService.ingest_webhook(payload, _sign(payload, stripe_secret))

        record = db.session.get(StripeWebhookEvent, event_id)
        assert record.status == StripeWebhookEventStatus.FAILED
