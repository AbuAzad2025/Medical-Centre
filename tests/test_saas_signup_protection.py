"""Tests for public SaaS signup abuse protections."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

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
from services.saas_registration_service import SaasRegistrationError, SaasRegistrationService
from tests.tenant_context import tenant_test_context


def _seed_package_version():
    pkg = Package(
        name='Starter',
        slug=f'starter-{uuid.uuid4().hex[:8]}',
        category='bundle',
        is_active=True,
    )
    db.session.add(pkg)
    db.session.flush()
    version = PackageVersion(
        package_id=pkg.id,
        version='1.0.0',
        trial_days=7,
        published_at=datetime.now(timezone.utc),
    )
    db.session.add(version)
    db.session.flush()
    db.session.add(PackageVersionPricing(
        package_version_id=version.id,
        billing_type='monthly',
        price=100,
        setup_fee=0,
        currency='SAR',
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


def _signup_kwargs(version_id, slug):
    return dict(
        slug=slug,
        name='Test Clinic',
        contact_email=f'{slug}@example.com',
        admin_username=f'admin_{slug}',
        admin_password='securepass1',
        admin_full_name='Admin',
        package_version_id=version_id,
    )


class TestSignupHoneypot:
    def test_honeypot_filled_rejects_bot(self, app):
        version = _seed_package_version()
        slug = f'bot-{uuid.uuid4().hex[:6]}'
        with tenant_test_context(app, bypass=True):
            with pytest.raises(SaasRegistrationError, match='bot_detected'):
                SaasRegistrationService.register_organization(
                    **_signup_kwargs(version.id, slug),
                    honeypot='http://spam.example',
                )


class TestSignupFloodLimit:
    def test_email_flood_limit_blocks_pending_signups(self, app):
        version = _seed_package_version()
        email = f'flood-{uuid.uuid4().hex[:6]}@example.com'
        now = datetime.now(timezone.utc)

        with tenant_test_context(app, bypass=True):
            for i in range(3):
                tenant = Tenant(
                    slug=f'pending-{uuid.uuid4().hex[:8]}',
                    name=f'Pending {i}',
                    contact_email=email,
                    status=TenantStatus.PENDING,
                    created_at=now,
                )
                db.session.add(tenant)
            db.session.commit()

            with pytest.raises(SaasRegistrationError, match='signup_flood_email'):
                SaasRegistrationService.register_organization(
                    slug=f'new-{uuid.uuid4().hex[:6]}',
                    name='Blocked',
                    contact_email=email,
                    admin_username='blocked_admin',
                    admin_password='securepass1',
                    admin_full_name='Blocked',
                    package_version_id=version.id,
                    client_ip='10.0.0.1',
                )


class TestSignupCaptcha:
    def test_captcha_skipped_when_no_secret(self, app, monkeypatch):
        monkeypatch.delenv('SIGNUP_CAPTCHA_SECRET', raising=False)
        version = _seed_package_version()
        slug = f'nocap-{uuid.uuid4().hex[:6]}'
        with tenant_test_context(app, bypass=True):
            tenant, _ = SaasRegistrationService.register_organization(
                **_signup_kwargs(version.id, slug),
                captcha_token=None,
            )
        assert tenant.slug == slug

    def test_captcha_required_when_secret_set(self, app, monkeypatch):
        monkeypatch.setenv('SIGNUP_CAPTCHA_SECRET', 'test-secret')
        version = _seed_package_version()
        slug = f'cap-{uuid.uuid4().hex[:6]}'
        with tenant_test_context(app, bypass=True):
            with pytest.raises(SaasRegistrationError, match='captcha_required'):
                SaasRegistrationService.register_organization(
                    **_signup_kwargs(version.id, slug),
                    captcha_token=None,
                )

    def test_captcha_verified_when_secret_and_token_valid(self, app, monkeypatch):
        monkeypatch.setenv('SIGNUP_CAPTCHA_SECRET', 'test-secret')
        version = _seed_package_version()
        slug = f'capok-{uuid.uuid4().hex[:6]}'
        with tenant_test_context(app, bypass=True):
            with patch.object(
                SaasRegistrationService,
                '_verify_captcha',
                side_effect=lambda token: None,
            ):
                tenant, _ = SaasRegistrationService.register_organization(
                    **_signup_kwargs(version.id, slug),
                    captcha_token='dummy-token',
                )
        assert tenant.slug == slug
