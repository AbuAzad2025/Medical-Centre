"""Unit tests for services.saas_registration_service.SaasRegistrationService."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

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
from services.saas_registration_service import SaasRegistrationError, SaasRegistrationService
from tests.tenant_context import tenant_test_context


def _seed_package_version(*, trial_days=7, price=100):
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
        trial_days=trial_days,
        published_at=datetime.now(timezone.utc),
    )
    db.session.add(version)
    db.session.flush()
    db.session.add(PackageVersionPricing(
        package_version_id=version.id,
        billing_type='monthly',
        price=price,
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


class TestRegistrationValidation:
    def test_invalid_slug_rejected(self, app):
        version = _seed_package_version()
        with tenant_test_context(app, bypass=True):
            with pytest.raises(SaasRegistrationError, match='invalid_slug'):
                SaasRegistrationService.register_organization(
                    **_signup_kwargs(version.id, 'Bad Slug!'),
                )

    def test_missing_required_fields(self, app):
        version = _seed_package_version()
        with tenant_test_context(app, bypass=True):
            with pytest.raises(SaasRegistrationError, match='missing_required_fields'):
                SaasRegistrationService.register_organization(
                    slug=f'ok-{uuid.uuid4().hex[:6]}',
                    name='',
                    contact_email='a@b.com',
                    admin_username='u',
                    admin_password='securepass1',
                    admin_full_name='A',
                    package_version_id=version.id,
                )

    def test_weak_password_rejected(self, app):
        version = _seed_package_version()
        slug = f'weak-{uuid.uuid4().hex[:6]}'
        kwargs = _signup_kwargs(version.id, slug)
        kwargs['admin_password'] = 'short'
        with tenant_test_context(app, bypass=True):
            with pytest.raises(SaasRegistrationError, match='weak_password'):
                SaasRegistrationService.register_organization(**kwargs)

    def test_duplicate_slug_rejected(self, app):
        version = _seed_package_version()
        slug = f'dup-{uuid.uuid4().hex[:6]}'
        with tenant_test_context(app, bypass=True):
            SaasRegistrationService.register_organization(**_signup_kwargs(version.id, slug))
            with pytest.raises(SaasRegistrationError, match='slug_taken'):
                SaasRegistrationService.register_organization(
                    slug=slug,
                    name='Other',
                    contact_email=f'other-{slug}@example.com',
                    admin_username=f'other_{slug}',
                    admin_password='securepass1',
                    admin_full_name='Other',
                    package_version_id=version.id,
                )


class TestPaymentRequiredPending:
    def test_no_trial_package_sets_pending_status(self, app, monkeypatch):
        monkeypatch.delenv('SAAS_REQUIRE_PAYMENT_AT_SIGNUP', raising=False)
        version = _seed_package_version(trial_days=0)
        slug = f'paid-{uuid.uuid4().hex[:6]}'
        with tenant_test_context(app, bypass=True):
            result = SaasRegistrationService.register_organization(**_signup_kwargs(version.id, slug))
        assert result.tenant.status == TenantStatus.PENDING

    def test_env_flag_forces_payment_required(self, app, monkeypatch):
        monkeypatch.setenv('SAAS_REQUIRE_PAYMENT_AT_SIGNUP', 'true')
        version = _seed_package_version(trial_days=14)
        slug = f'envpay-{uuid.uuid4().hex[:6]}'
        with tenant_test_context(app, bypass=True):
            result = SaasRegistrationService.register_organization(**_signup_kwargs(version.id, slug))
        assert result.tenant.status == TenantStatus.PENDING

    def test_checkout_url_when_stripe_configured(self, app, monkeypatch):
        monkeypatch.setenv('STRIPE_SECRET_KEY', 'sk_test_reg')
        version = _seed_package_version(trial_days=0)
        slug = f'chk-{uuid.uuid4().hex[:6]}'
        with tenant_test_context(app, bypass=True):
            with patch.object(
                SaasRegistrationService,
                '_maybe_create_checkout',
                return_value='https://checkout.stripe.test/session',
            ):
                result = SaasRegistrationService.register_organization(**_signup_kwargs(version.id, slug))
        assert result.checkout_url == 'https://checkout.stripe.test/session'


class TestSignupAbuseProtections:
    def test_honeypot_rejects_bot(self, app):
        version = _seed_package_version()
        slug = f'bot-{uuid.uuid4().hex[:6]}'
        with tenant_test_context(app, bypass=True):
            with pytest.raises(SaasRegistrationError, match='bot_detected'):
                SaasRegistrationService.register_organization(
                    **_signup_kwargs(version.id, slug),
                    honeypot='http://spam.example',
                )

    def test_email_flood_limit(self, app):
        version = _seed_package_version()
        email = f'flood-{uuid.uuid4().hex[:6]}@example.com'
        now = datetime.now(timezone.utc)
        with tenant_test_context(app, bypass=True):
            for i in range(3):
                db.session.add(Tenant(
                    slug=f'pending-{uuid.uuid4().hex[:8]}',
                    name=f'Pending {i}',
                    contact_email=email,
                    status=TenantStatus.PENDING,
                    created_at=now,
                ))
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
                )

    def test_ip_flood_limit(self, app):
        version = _seed_package_version()
        client_ip = f'10.99.{uuid.uuid4().hex[:2]}.{uuid.uuid4().hex[:2]}'
        now = datetime.now(timezone.utc)
        with tenant_test_context(app, bypass=True):
            for i in range(10):
                db.session.add(Tenant(
                    slug=f'ip-{uuid.uuid4().hex[:8]}',
                    name=f'IP {i}',
                    contact_email=f'ip{i}@example.com',
                    status=TenantStatus.PENDING,
                    created_at=now,
                    settings={'signup_ip': client_ip},
                ))
            db.session.commit()
            with pytest.raises(SaasRegistrationError, match='signup_flood_ip'):
                SaasRegistrationService.register_organization(
                    slug=f'ipblock-{uuid.uuid4().hex[:6]}',
                    name='Blocked IP',
                    contact_email=f'new-{uuid.uuid4().hex[:6]}@example.com',
                    admin_username='ip_admin',
                    admin_password='securepass1',
                    admin_full_name='Blocked',
                    package_version_id=version.id,
                    client_ip=client_ip,
                )


class TestRegistrationProvisioning:
    def test_provisioning_error_wrapped(self, app):
        from app.core.saas.lifecycle import ProvisioningError, TenantProvisioningService

        version = _seed_package_version()
        slug = f'prov-{uuid.uuid4().hex[:6]}'
        with tenant_test_context(app, bypass=True):
            with patch.object(
                TenantProvisioningService,
                'provision_tenant',
                side_effect=ProvisioningError('package_unavailable'),
            ):
                with pytest.raises(SaasRegistrationError, match='package_unavailable'):
                    SaasRegistrationService.register_organization(**_signup_kwargs(version.id, slug))

    def test_client_ip_stored_in_tenant_settings(self, app):
        version = _seed_package_version()
        slug = f'ip-{uuid.uuid4().hex[:6]}'
        client_ip = '203.0.113.50'
        with tenant_test_context(app, bypass=True):
            result = SaasRegistrationService.register_organization(
                **_signup_kwargs(version.id, slug),
                client_ip=client_ip,
            )
        assert result.tenant.settings.get('signup_ip') == client_ip


class TestResolveDefaultPackage:
    def test_env_override(self, app, monkeypatch):
        monkeypatch.setenv('SAAS_DEFAULT_PACKAGE_VERSION_ID', '42')
        assert SaasRegistrationService.resolve_default_package_version_id() == 42

    def test_no_available_package_raises(self, app, monkeypatch):
        monkeypatch.delenv('SAAS_DEFAULT_PACKAGE_VERSION_ID', raising=False)
        with patch.object(
            PackageVersion,
            'query',
            new_callable=MagicMock,
        ) as mock_query:
            mock_query.join.return_value.filter.return_value.order_by.return_value.first.return_value = None
            with pytest.raises(SaasRegistrationError, match='no_default_package'):
                SaasRegistrationService.resolve_default_package_version_id()


class TestCaptchaVerification:
    def test_captcha_http_failure_raises(self, app, monkeypatch):
        monkeypatch.setenv('SIGNUP_CAPTCHA_SECRET', 'test-secret')
        with patch('urllib.request.urlopen', side_effect=OSError('network down')):
            with pytest.raises(SaasRegistrationError, match='captcha_failed'):
                SaasRegistrationService._verify_captcha('token')

    def test_captcha_invalid_response_raises(self, app, monkeypatch):
        monkeypatch.setenv('SIGNUP_CAPTCHA_SECRET', 'test-secret')
        fake_resp = MagicMock()
        fake_resp.read.return_value = b'{"success": false}'
        fake_resp.__enter__ = lambda s: s
        fake_resp.__exit__ = MagicMock(return_value=False)
        with patch('urllib.request.urlopen', return_value=fake_resp):
            with pytest.raises(SaasRegistrationError, match='captcha_failed'):
                SaasRegistrationService._verify_captcha('bad-token')


class TestMaybeCreateCheckout:
    def test_creates_checkout_session_end_to_end(self, app, monkeypatch):
        monkeypatch.setenv('STRIPE_SECRET_KEY', 'sk_test_checkout')
        version = _seed_package_version(trial_days=0)
        slug = f'co-{uuid.uuid4().hex[:6]}'
        with tenant_test_context(app, bypass=True):
            result = SaasRegistrationService.register_organization(**_signup_kwargs(version.id, slug))
        with patch(
            'services.stripe_billing_service.StripeBillingService.create_checkout_session',
            return_value={'url': 'https://checkout.stripe.test/x'},
        ):
            url = SaasRegistrationService._maybe_create_checkout(
                result.tenant, version.id, 'monthly',
            )
        assert url == 'https://checkout.stripe.test/x'
