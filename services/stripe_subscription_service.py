"""Stripe subscription webhook integration for SaaS billing lifecycle."""
from __future__ import annotations

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

import stripe

from app.extensions import db
from app.core.saas.lifecycle import TenantProvisioningService
from app.core.saas.models import StripeWebhookEvent, StripeWebhookEventStatus
from app.core.saas.projection import EntitlementProjectionService
from app.core.tenant.models import Tenant, TenantStatus

logger = logging.getLogger(__name__)


class StripeWebhookError(ValueError):
    """Invalid signature or payload."""


class StripeSubscriptionService:
    """Map Stripe billing events to tenant subscription state + entitlements."""

    @classmethod
    def webhook_secret(cls) -> str:
        secret = os.environ.get('STRIPE_WEBHOOK_SECRET', '').strip()
        if not secret:
            raise StripeWebhookError('stripe_webhook_not_configured')
        return secret

    @classmethod
    def verify_signature(cls, payload: bytes, signature_header: str) -> dict:
        secret = cls.webhook_secret()
        try:
            event = stripe.Webhook.construct_event(payload, signature_header, secret)
        except stripe.SignatureVerificationError as exc:
            raise StripeWebhookError('signature_mismatch') from exc
        except Exception as exc:
            raise StripeWebhookError('invalid_signature_header') from exc
        return event

    @classmethod
    def _tenant_from_event(cls, event: dict[str, Any]) -> Optional[Tenant]:
        obj = event.get('data', {}).get('object', {})
        metadata = obj.get('metadata') or {}
        tenant_id = metadata.get('tenant_id')
        if tenant_id:
            return Tenant.query.get(int(tenant_id))
        customer_id = obj.get('customer')
        if customer_id:
            for candidate in Tenant.query.filter(Tenant.settings.isnot(None)).all():
                if (candidate.settings or {}).get('stripe_customer_id') == customer_id:
                    return candidate
        return None

    @classmethod
    def _store_stripe_refs(cls, tenant: Tenant, *, customer_id: str | None = None, subscription_id: str | None = None) -> None:
        settings = dict(tenant.settings or {})
        if customer_id:
            settings['stripe_customer_id'] = customer_id
        if subscription_id:
            settings['stripe_subscription_id'] = subscription_id
        tenant.settings = settings
        db.session.add(tenant)

    @classmethod
    def handle_event(cls, event: dict[str, Any]) -> dict[str, Any]:
        event_type = event.get('type', '')
        tenant = cls._tenant_from_event(event)
        obj = event.get('data', {}).get('object', {})

        if event_type == 'checkout.session.completed':
            if tenant is None:
                return {'ignored': True, 'reason': 'tenant_not_found'}
            cls._store_stripe_refs(
                tenant,
                customer_id=obj.get('customer'),
                subscription_id=obj.get('subscription'),
            )
            tenant.status = TenantStatus.ACTIVE
            db.session.commit()
            EntitlementProjectionService.calculate(tenant.id)
            return {'tenant_id': tenant.id, 'action': 'checkout_completed'}

        if event_type == 'customer.subscription.created':
            if tenant is None:
                return {'ignored': True, 'reason': 'tenant_not_found'}
            cls._store_stripe_refs(
                tenant,
                customer_id=obj.get('customer'),
                subscription_id=obj.get('id'),
            )
            if obj.get('status') in ('active', 'trialing'):
                tenant.status = TenantStatus.ACTIVE
            db.session.commit()
            EntitlementProjectionService.calculate(tenant.id)
            return {'tenant_id': tenant.id, 'action': 'subscription_created'}

        if event_type == 'customer.subscription.updated':
            if tenant is None:
                return {'ignored': True, 'reason': 'tenant_not_found'}
            status = obj.get('status')
            cls._store_stripe_refs(tenant, subscription_id=obj.get('id'))
            if status in ('active', 'trialing'):
                TenantProvisioningService.reactivate_tenant(tenant.id)
            elif status in ('past_due', 'unpaid'):
                TenantProvisioningService.suspend_tenant(tenant.id, reason=f'stripe:{status}')
            elif status == 'canceled':
                TenantProvisioningService.cancel_tenant(tenant.id)
            db.session.commit()
            EntitlementProjectionService.calculate(tenant.id)
            return {'tenant_id': tenant.id, 'action': 'subscription_updated', 'stripe_status': status}

        if event_type == 'customer.subscription.deleted':
            if tenant is None:
                return {'ignored': True, 'reason': 'tenant_not_found'}
            TenantProvisioningService.cancel_tenant(tenant.id)
            db.session.commit()
            EntitlementProjectionService.calculate(tenant.id)
            return {'tenant_id': tenant.id, 'action': 'subscription_deleted'}

        if event_type == 'invoice.payment_failed':
            if tenant is None:
                return {'ignored': True, 'reason': 'tenant_not_found'}
            TenantProvisioningService.suspend_tenant(tenant.id, reason='stripe:payment_failed')
            db.session.commit()
            EntitlementProjectionService.calculate(tenant.id)
            return {'tenant_id': tenant.id, 'action': 'payment_failed'}

        if event_type == 'invoice.paid':
            if tenant is None:
                return {'ignored': True, 'reason': 'tenant_not_found'}
            TenantProvisioningService.reactivate_tenant(tenant.id)
            line_id = (tenant.settings or {}).get('stripe_base_line_id')
            if line_id:
                try:
                    TenantProvisioningService.renew_base_line(int(line_id))
                except Exception as exc:
                    logger.warning('Stripe renew_base_line skipped tenant=%s: %s', tenant.id, exc)
            db.session.commit()
            EntitlementProjectionService.calculate(tenant.id)
            return {'tenant_id': tenant.id, 'action': 'invoice_paid'}

        return {'ignored': True, 'reason': 'unsupported_event', 'type': event_type}

    @classmethod
    def _check_idempotency(cls, event_id: str) -> Optional[StripeWebhookEvent]:
        return db.session.get(StripeWebhookEvent, event_id)

    @classmethod
    def ingest_webhook(cls, payload: bytes, signature_header: str) -> dict[str, Any]:
        event = cls.verify_signature(payload, signature_header)

        if not isinstance(event, dict) or 'type' not in event:
            raise StripeWebhookError('invalid_event_payload')

        event_id = event.get('id', '')
        if not event_id:
            raise StripeWebhookError('missing_event_id')

        existing = cls._check_idempotency(event_id)
        if existing:
            return {'already_processed': True, 'event_id': event_id, 'status': existing.status}

        payload_hash = hashlib.sha256(payload).hexdigest()
        record = StripeWebhookEvent(
            event_id=event_id,
            status=StripeWebhookEventStatus.PROCESSING,
            payload_hash=payload_hash,
        )
        db.session.add(record)
        db.session.flush()

        try:
            result = cls.handle_event(event)
            record.status = StripeWebhookEventStatus.PROCESSED
            record.processed_at = datetime.now(timezone.utc)
            db.session.commit()
            return result
        except Exception as exc:
            db.session.rollback()
            try:
                failed_record = db.session.get(StripeWebhookEvent, event_id)
                if failed_record:
                    failed_record.status = StripeWebhookEventStatus.FAILED
                    failed_record.error_message = str(exc)[:1000]
                else:
                    db.session.add(StripeWebhookEvent(
                        event_id=event_id,
                        status=StripeWebhookEventStatus.FAILED,
                        payload_hash=payload_hash,
                        error_message=str(exc)[:1000],
                    ))
                db.session.commit()
            except Exception:
                db.session.rollback()
            raise
