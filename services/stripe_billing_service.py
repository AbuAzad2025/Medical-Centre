"""Outbound Stripe billing API for self-service SaaS subscription management."""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

import stripe

from app.extensions import db
from app.core.saas.lifecycle import TenantProvisioningService
from app.core.saas.models import PackageVersion, PackageVersionPricing
from app.core.saas.projection import EntitlementProjectionService
from app.core.tenant.models import Tenant

logger = logging.getLogger(__name__)


class StripeBillingError(ValueError):
    """Raised when Stripe outbound billing operations fail."""


class StripeBillingService:
    """Create and manage Stripe subscriptions; sync entitlements locally."""

    @classmethod
    def _version_display_name(cls, version: PackageVersion) -> str:
        package = getattr(version, 'package', None)
        if package is not None and getattr(package, 'name', None):
            return package.name
        return f'package-{version.id}-v{version.version}'

    @classmethod
    def _api_key(cls) -> str:
        key = os.environ.get('STRIPE_SECRET_KEY', '').strip()
        if not key:
            raise StripeBillingError('stripe_secret_not_configured')
        stripe.api_key = key
        return key

    @classmethod
    def _require_tenant(cls, tenant_id: int) -> Tenant:
        tenant = Tenant.query.get(tenant_id)
        if tenant is None:
            raise StripeBillingError('tenant_not_found')
        return tenant

    @classmethod
    def _pricing_for(cls, package_version_id: int, billing_type: str) -> PackageVersionPricing:
        pricing = PackageVersionPricing.query.filter_by(
            package_version_id=package_version_id,
            billing_type=billing_type,
        ).first()
        if pricing is None:
            raise StripeBillingError('package_pricing_not_found')
        return pricing

    @classmethod
    def _store_stripe_refs(
        cls,
        tenant: Tenant,
        *,
        customer_id: str | None = None,
        subscription_id: str | None = None,
    ) -> None:
        settings = dict(tenant.settings or {})
        if customer_id:
            settings['stripe_customer_id'] = customer_id
        if subscription_id:
            settings['stripe_subscription_id'] = subscription_id
        tenant.settings = settings
        db.session.add(tenant)

    @classmethod
    def ensure_customer(cls, tenant_id: int) -> str:
        cls._api_key()
        tenant = cls._require_tenant(tenant_id)
        existing = (tenant.settings or {}).get('stripe_customer_id')
        if existing:
            return existing

        customer = stripe.Customer.create(
            email=tenant.contact_email,
            name=tenant.name,
            metadata={'tenant_id': str(tenant.id), 'tenant_slug': tenant.slug},
        )
        cls._store_stripe_refs(tenant, customer_id=customer.id)
        db.session.commit()
        return customer.id

    @classmethod
    def create_checkout_session(
        cls,
        tenant_id: int,
        package_version_id: int,
        billing_type: str,
        *,
        success_url: str,
        cancel_url: str,
    ) -> dict[str, Any]:
        cls._api_key()
        tenant = cls._require_tenant(tenant_id)
        version = PackageVersion.query.get(package_version_id)
        if version is None:
            raise StripeBillingError('package_version_not_found')

        pricing = cls._pricing_for(package_version_id, billing_type)
        customer_id = cls.ensure_customer(tenant_id)
        interval = 'month' if billing_type == 'monthly' else 'year'
        amount_cents = int(float(pricing.price) * 100)

        session = stripe.checkout.Session.create(
            customer=customer_id,
            mode='subscription',
            success_url=success_url,
            cancel_url=cancel_url,
            line_items=[{
                'price_data': {
                    'currency': os.environ.get('STRIPE_CURRENCY', 'usd'),
                    'product_data': {'name': cls._version_display_name(version)},
                    'recurring': {'interval': interval},
                    'unit_amount': amount_cents,
                },
                'quantity': 1,
            }],
            metadata={
                'tenant_id': str(tenant.id),
                'package_version_id': str(package_version_id),
                'billing_type': billing_type,
            },
            subscription_data={
                'metadata': {
                    'tenant_id': str(tenant.id),
                    'package_version_id': str(package_version_id),
                    'billing_type': billing_type,
                },
            },
        )
        return {'checkout_session_id': session.id, 'url': session.url}

    @classmethod
    def create_billing_portal_session(cls, tenant_id: int, *, return_url: str) -> dict[str, str]:
        cls._api_key()
        customer_id = cls.ensure_customer(tenant_id)
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )
        return {'url': session.url}

    @classmethod
    def cancel_subscription(cls, tenant_id: int, *, at_period_end: bool = True) -> dict[str, Any]:
        cls._api_key()
        tenant = cls._require_tenant(tenant_id)
        subscription_id = (tenant.settings or {}).get('stripe_subscription_id')
        if not subscription_id:
            raise StripeBillingError('stripe_subscription_missing')

        if at_period_end:
            subscription = stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True,
            )
        else:
            subscription = stripe.Subscription.cancel(subscription_id)

        TenantProvisioningService.cancel_tenant(tenant_id)
        db.session.commit()
        EntitlementProjectionService.calculate(tenant_id)
        return {
            'subscription_id': subscription.id,
            'status': subscription.status,
            'cancel_at_period_end': getattr(subscription, 'cancel_at_period_end', False),
        }

    @classmethod
    def change_plan(
        cls,
        tenant_id: int,
        new_package_version_id: int,
        billing_type: str,
        *,
        performed_by_user_id: Optional[int] = None,
    ) -> dict[str, Any]:
        cls._api_key()
        tenant = cls._require_tenant(tenant_id)
        subscription_id = (tenant.settings or {}).get('stripe_subscription_id')

        new_pricing = cls._pricing_for(new_package_version_id, billing_type)
        new_version = PackageVersion.query.get(new_package_version_id)
        if new_version is None:
            raise StripeBillingError('package_version_not_found')

        if subscription_id:
            subscription = stripe.Subscription.retrieve(subscription_id)
            item_id = subscription['items']['data'][0]['id']
            interval = 'month' if billing_type == 'monthly' else 'year'
            stripe.Subscription.modify(
                subscription_id,
                items=[{
                    'id': item_id,
                    'price_data': {
                        'currency': os.environ.get('STRIPE_CURRENCY', 'usd'),
                        'product_data': {'name': cls._version_display_name(new_version)},
                        'recurring': {'interval': interval},
                        'unit_amount': int(float(new_pricing.price) * 100),
                    },
                }],
                proration_behavior='create_prorations',
                metadata={
                    'tenant_id': str(tenant.id),
                    'package_version_id': str(new_package_version_id),
                    'billing_type': billing_type,
                },
            )

        from app.core.saas.models import SubscriptionLine, SubscriptionLineStatus, SubscriptionLineType
        current_line = SubscriptionLine.query.filter_by(
            tenant_id=tenant_id,
            line_type=SubscriptionLineType.BASE,
            status=SubscriptionLineStatus.ACTIVE,
        ).first()
        current_price = 0.0
        if current_line:
            current_pricing = cls._pricing_for(current_line.package_version_id, current_line.billing_type)
            current_price = float(current_pricing.price)

        if float(new_pricing.price) >= current_price:
            line = TenantProvisioningService.upgrade_tenant(
                tenant_id,
                new_package_version_id,
                billing_type,
                performed_by_user_id=performed_by_user_id,
            )
            action = 'upgrade'
        else:
            line = TenantProvisioningService.downgrade_tenant(
                tenant_id,
                new_package_version_id,
                billing_type,
                performed_by_user_id=performed_by_user_id,
            )
            action = 'downgrade'

        cls._store_stripe_refs(tenant, subscription_id=subscription_id)
        db.session.commit()
        EntitlementProjectionService.calculate(tenant_id)
        return {
            'action': action,
            'subscription_line_id': line.id,
            'package_version_id': new_package_version_id,
        }
