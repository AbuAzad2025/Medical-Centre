"""Outbound Stripe billing API for self-service SaaS subscription management."""
from __future__ import annotations

import logging
import os
import uuid
from decimal import Decimal
from typing import Any, Optional

import stripe

from app.extensions import db
from utils.db_safety import safe_commit
from utils.circuit_breaker import circuit_breaker_call
from app.core.saas.lifecycle import TenantProvisioningService, ProvisioningError
from app.core.saas.models import (
    PackageVersion,
    PackageVersionAvailability,
    PackageVersionAvailabilityStatus,
    PackageVersionPricing,
    SubscriptionLine,
    SubscriptionLineStatus,
    SubscriptionLineType,
)
from app.core.saas.projection import EntitlementProjectionService
from app.core.tenant.models import Tenant, TenantStatus
from sqlalchemy import select

logger = logging.getLogger(__name__)


class StripeBillingError(ValueError):
    """Raised when Stripe outbound billing operations fail."""


class PlanChangeValidationError(StripeBillingError):
    """Raised when a plan change fails pre-flight validation."""


class StripeBillingService:
    """Create and manage Stripe subscriptions; sync entitlements locally."""

    # Allowed tenant statuses for plan changes
    _PLAN_CHANGE_ALLOWED_STATUSES = {TenantStatus.ACTIVE, TenantStatus.TRIAL}

    @staticmethod
    def _cb_call(func, *args, **kwargs):
        """Route external calls through circuit breaker."""
        return circuit_breaker_call('stripe_billing', func, *args, **kwargs)

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
        tenant = db.session.get(Tenant, tenant_id)  # global reference table - no tenant scope
        if tenant is None:
            raise StripeBillingError('tenant_not_found')
        return tenant

    @classmethod
    def _pricing_for(cls, package_version_id: int, billing_type: str) -> PackageVersionPricing:
        pricing = db.session.execute(select(PackageVersionPricing).filter_by(
            package_version_id=package_version_id,
            billing_type=billing_type,
        )).scalars().first()
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

    # ── Validation helpers ──────────────────────────────────────────

    @classmethod
    def _validate_target_version(cls, package_version_id: int) -> PackageVersion:
        """Ensure target package version is available (not deprecated/retired)."""
        version = db.session.get(PackageVersion, package_version_id)
        if not version:
            raise PlanChangeValidationError('package_version_not_found')
        if version.is_deprecated:
            raise PlanChangeValidationError('package_version_deprecated')
        latest_availability = db.session.execute(
            select(PackageVersionAvailability)
            .filter_by(package_version_id=version.id)
            .order_by(PackageVersionAvailability.effective_from.desc())
        ).scalars().first()
        if latest_availability and latest_availability.availability_status == PackageVersionAvailabilityStatus.RETIRED:
            raise PlanChangeValidationError('package_version_retired')
        return version

    @classmethod
    def _validate_plan_change(
        cls,
        tenant: Tenant,
        new_package_version_id: int,
        billing_type: str,
    ) -> tuple[PackageVersion, PackageVersionPricing, Decimal]:
        """Pre-flight validation before any Stripe API call.

        Returns (new_version, new_pricing, current_price) on success.
        Raises PlanChangeValidationError on any violation.
        """
        # 1. Tenant status must allow plan changes
        if tenant.status not in cls._PLAN_CHANGE_ALLOWED_STATUSES:
            raise PlanChangeValidationError(
                f"Plan changes not allowed for tenant status '{tenant.status.value}'. "
                f"Allowed: {[s.value for s in cls._PLAN_CHANGE_ALLOWED_STATUSES]}"
            )

        # 2. Target version must be available (not deprecated/retired)
        new_version = cls._validate_target_version(new_package_version_id)

        # 3. Target pricing must exist for requested billing type
        new_pricing = cls._pricing_for(new_package_version_id, billing_type)
        if new_pricing.price is None or Decimal(str(new_pricing.price)) < 0:
            raise PlanChangeValidationError('package_pricing_invalid')

        # 4. Current base line pricing for proration comparison
        current_price = Decimal('0')
        current_line = db.session.execute(
            select(SubscriptionLine).filter_by(
                tenant_id=tenant.id,
                line_type=SubscriptionLineType.BASE,
                status=SubscriptionLineStatus.ACTIVE,
            )
        ).scalars().first()
        if current_line:
            try:
                current_pricing = cls._pricing_for(current_line.package_version_id, current_line.billing_type)
                current_price = Decimal(str(current_pricing.price or 0))
            except StripeBillingError:
                current_price = Decimal('0')

        # 5. If tenant has a Stripe subscription, check for pending invoices
        subscription_id = (tenant.settings or {}).get('stripe_subscription_id')
        if subscription_id:
            try:
                open_invoices = stripe.Invoice.list(
                    subscription=subscription_id,
                    status='open',
                    limit=1,
                )
                if open_invoices.get('data'):
                    raise PlanChangeValidationError(
                        'pending_invoices_exist: settle or void open invoices before plan change'
                    )
            except PlanChangeValidationError:
                raise  # Re-raise validation errors — these are fatal
            except Exception as e:
                logger.warning(
                    'Stripe invoice list failed for tenant=%s sub=%s: %s',
                    tenant.id, subscription_id, e,
                )
                # Non-fatal: if we can't verify, we proceed with caution

        return new_version, new_pricing, current_price

    @classmethod
    def _validate_proration(cls, subscription_id: str) -> None:
        """After a Stripe plan change, verify no negative invoice balances exist."""
        try:
            # Stripe SDK API varies by version: upcoming() vs retrieve_upcoming()
            upcoming = None
            if hasattr(stripe.Invoice, 'upcoming'):
                upcoming = stripe.Invoice.upcoming(subscription=subscription_id)
            elif hasattr(stripe.Invoice, 'retrieve_upcoming'):
                upcoming = stripe.Invoice.retrieve_upcoming(subscription=subscription_id)
            if upcoming:
                amount_due = getattr(upcoming, 'amount_due', 0) or 0
                if amount_due < 0:
                    logger.warning(
                        'Proration produced negative upcoming invoice: sub=%s amount_due=%s',
                        subscription_id, amount_due,
                    )
                    # We do NOT raise here — negative proration credits are valid in Stripe.
                    # We only log for monitoring. If the business wants to block this,
                    # change this to raise StripeBillingError.
        except Exception as e:
            logger.warning('Upcoming invoice check failed for sub=%s: %s', subscription_id, e)

    # ── Public methods ──────────────────────────────────────────────

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
        safe_commit(db.session, error_message="فشل حفظ عميل Stripe", reraise=True)
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
        version = db.session.get(PackageVersion, package_version_id)  # global reference table - no tenant scope
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
            if getattr(subscription, 'status', None) in ('canceled', 'cancelled'):
                TenantProvisioningService.cancel_tenant(tenant_id)
                EntitlementProjectionService.calculate(tenant_id)
            safe_commit(db.session, error_message="فشل إلغاء الاشتراك (نهاية الفترة)", reraise=True)
            return {
                'subscription_id': subscription.id,
                'status': subscription.status,
                'cancel_at_period_end': True,
            }

        subscription = stripe.Subscription.cancel(subscription_id)
        TenantProvisioningService.cancel_tenant(tenant_id)
        safe_commit(db.session, error_message="فشل إلغاء الاشتراك", reraise=True)
        EntitlementProjectionService.calculate(tenant_id)
        return {
            'subscription_id': subscription.id,
            'status': subscription.status,
            'cancel_at_period_end': False,
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

        # ── Pre-flight validation (before any Stripe API call) ─────────
        new_version, new_pricing, current_price = cls._validate_plan_change(
            tenant, new_package_version_id, billing_type
        )
        subscription_id = (tenant.settings or {}).get('stripe_subscription_id')
        new_price_decimal = Decimal(str(new_pricing.price))

        # ── Stripe subscription modification ─────────────────────────
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
                idempotency_key=f'plan_change_{tenant_id}_{new_package_version_id}_{billing_type}_{uuid.uuid4().hex[:16]}',
            )

            # Validate proration doesn't produce unreasonably negative balances
            cls._validate_proration(subscription_id)

        # ── Local entitlement update ───────────────────────────────────
        # Trial → paid conversion: if tenant was on trial, mark ACTIVE
        was_trial = tenant.status == TenantStatus.TRIAL

        if new_price_decimal >= current_price:
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

        # If this was a trial conversion, explicitly update tenant status
        if was_trial and tenant.status != TenantStatus.ACTIVE:
            tenant.status = TenantStatus.ACTIVE
            db.session.add(tenant)

        cls._store_stripe_refs(tenant, subscription_id=subscription_id)
        safe_commit(db.session, error_message="فشل تغيير خطة الاشتراك", reraise=True)
        EntitlementProjectionService.calculate(tenant_id)
        return {
            'action': action,
            'subscription_line_id': line.id,
            'package_version_id': new_package_version_id,
            'trial_converted': was_trial,
        }
