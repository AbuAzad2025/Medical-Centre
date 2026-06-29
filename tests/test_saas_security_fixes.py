"""Security and SaaS completeness regression tests."""

import uuid
from datetime import datetime, timezone

import pytest

from app.extensions import db
from app.core.saas.models import (
    Package,
    PackageVersion,
    PackageVersionAvailability,
    PackageVersionAvailabilityStatus,
    PackageVersionEntitlement,
    PackageVersionPricing,
)
from app.core.tenant.models import Tenant
from app.shared.enums import TenantStatus
from models.user import User
from tests.tenant_context import tenant_test_context


def _seed_trial_package():
    pkg = Package(
        name='TrialPkg',
        slug=f'trial-{uuid.uuid4().hex[:8]}',
        category='bundle',
        is_active=True,
    )
    db.session.add(pkg)
    db.session.flush()
    version = PackageVersion(
        package_id=pkg.id,
        version='1.0.0',
        trial_days=14,
        published_at=datetime.now(timezone.utc),
    )
    db.session.add(version)
    db.session.flush()
    db.session.add(PackageVersionPricing(
        package_version_id=version.id,
        billing_type='monthly',
        price=99,
        setup_fee=0,
        currency='USD',
    ))
    db.session.add(PackageVersionEntitlement(
        package_version_id=version.id,
        module_name='reception',
        capability_key='reception.access',
    ))
    db.session.add(PackageVersionAvailability(
        package_version_id=version.id,
        availability_status=PackageVersionAvailabilityStatus.AVAILABLE,
        effective_from=datetime.now(timezone.utc),
    ))
    db.session.commit()
    return version


class TestTrialTenantLogin:
    def test_trial_slug_resolves_for_login(self, app):
        from app.core.tenant.middleware import _get_tenant_by_slug
        from services.saas_registration_service import SaasRegistrationService

        version = _seed_trial_package()
        slug = f'trial-login-{uuid.uuid4().hex[:8]}'
        tenant, admin = SaasRegistrationService.register_organization(
            slug=slug,
            name='Trial Clinic',
            contact_email=f'{slug}@test.local',
            admin_username=f'admin_{slug[:8]}',
            admin_password='SecurePass1!',
            admin_full_name='Trial Admin',
            package_version_id=version.id,
        )
        assert tenant.status == TenantStatus.TRIAL
        with app.app_context():
            resolved = _get_tenant_by_slug(slug)
            assert resolved is not None
            assert resolved.id == tenant.id

    def test_trial_tenant_login_flow(self, app, client, monkeypatch):
        monkeypatch.setenv('ENABLE_SAAS_MODE', 'true')
        version = _seed_trial_package()
        slug = f'trial-flow-{uuid.uuid4().hex[:8]}'
        username = f'user_{slug[:8]}'
        from services.saas_registration_service import SaasRegistrationService
        SaasRegistrationService.register_organization(
            slug=slug,
            name='Trial Flow Clinic',
            contact_email=f'{slug}@test.local',
            admin_username=username,
            admin_password='SecurePass1!',
            admin_full_name='Trial Admin',
            package_version_id=version.id,
        )
        from app.core.rate_limiter import _shared_store
        _shared_store.clear()
        resp = client.post('/auth/login', data={
            'username': username,
            'password': 'SecurePass1!',
            'tenant_slug': slug,
        })
        assert resp.status_code in (200, 302)


class TestStripeWebhookCsrf:
    def test_webhook_not_blocked_by_csrf(self, app, client, monkeypatch):
        monkeypatch.setenv('STRIPE_WEBHOOK_SECRET', 'whsec_test')
        monkeypatch.setattr(
            'services.stripe_subscription_service.StripeSubscriptionService.ingest_webhook',
            lambda payload, sig: {'received': True},
        )
        resp = client.post(
            '/api/billing/stripe/webhook',
            data=b'{}',
            headers={'Stripe-Signature': 't=1,v1=test'},
            content_type='application/json',
        )
        assert resp.status_code == 200


class TestPerTenantUsername:
    def test_same_username_different_tenants_allowed(self, app):
        from services.saas_registration_service import SaasRegistrationService

        version = _seed_trial_package()
        shared = f'shared_{uuid.uuid4().hex[:8]}'
        slug_a = f'ta-{uuid.uuid4().hex[:6]}'
        slug_b = f'tb-{uuid.uuid4().hex[:6]}'
        SaasRegistrationService.register_organization(
            slug=slug_a, name='A', contact_email=f'{slug_a}@a.test',
            admin_username=shared, admin_password='SecurePass1!',
            admin_full_name='Admin A', package_version_id=version.id,
        )
        tenant_b, _ = SaasRegistrationService.register_organization(
            slug=slug_b, name='B', contact_email=f'{slug_b}@b.test',
            admin_username=shared, admin_password='SecurePass1!',
            admin_full_name='Admin B', package_version_id=version.id,
        )
        with app.app_context(), app.test_request_context():
            from flask import g
            g._tenant_filter_bypass = True
            count = User.query.filter_by(username=shared).count()
            assert count == 2
            assert tenant_b.id is not None
