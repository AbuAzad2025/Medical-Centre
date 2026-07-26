"""Automated SaaS self-service tenant registration (S0 provisioning loop)."""
from __future__ import annotations

import json
import logging
import os
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterator, Optional, Tuple

from flask import g, has_request_context, request

from app.extensions import db
from utils.db_safety import safe_commit
from app.core.saas.lifecycle import ProvisioningError, TenantProvisioningService
from app.core.saas.models import PackageVersion, PackageVersionAvailability, PackageVersionAvailabilityStatus
from app.core.tenant.models import Tenant, PlatformAuditLog
from app.shared.enums import TenantStatus
from models.user import User
from sqlalchemy import select

logger = logging.getLogger(__name__)

_SLUG_RE = re.compile(r'^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$')
_SIGNUP_FLOOD_EMAIL_LIMIT = 3
_SIGNUP_FLOOD_IP_LIMIT = 10
_SIGNUP_FLOOD_WINDOW = timedelta(hours=1)


class SaasRegistrationError(ValueError):
    """Validation or provisioning failure for public signup."""


@dataclass
class RegistrationResult:
    tenant: Tenant
    admin: User
    checkout_url: Optional[str] = None

    def __iter__(self) -> Iterator:
        yield self.tenant
        yield self.admin


class SaasRegistrationService:
    """Provision an isolated tenant + primary admin without manual owner intervention."""

    DEFAULT_ADMIN_ROLE = 'manager'

    @staticmethod
    def _with_tenant_bypass(fn):
        """Run cross-tenant lookups (global username/email) during public signup."""
        if not has_request_context():
            return fn()
        prev = g.get('_tenant_filter_bypass', False)
        g._tenant_filter_bypass = True
        try:
            return fn()
        finally:
            if prev:
                g._tenant_filter_bypass = True
            else:
                g.pop('_tenant_filter_bypass', None)

    @classmethod
    def _validate_bot_fields(cls, honeypot: str | None) -> None:
        if honeypot and str(honeypot).strip():
            raise SaasRegistrationError('bot_detected')

    @classmethod
    def _verify_captcha(cls, token: str | None) -> None:
        secret = os.environ.get('SIGNUP_CAPTCHA_SECRET', '').strip()
        if not secret:
            return
        if not token or not str(token).strip():
            raise SaasRegistrationError('captcha_required')
        payload = urllib.parse.urlencode({
            'secret': secret,
            'response': token.strip(),
        }).encode()
        req = urllib.request.Request(
            'https://challenges.cloudflare.com/turnstile/v0/siteverify',
            data=payload,
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode())
        except Exception as exc:
            logger.warning('Captcha verification request failed: %s', exc)
            raise SaasRegistrationError('captcha_failed') from exc
        if not result.get('success'):
            raise SaasRegistrationError('captcha_failed')

    @classmethod
    def _check_signup_flood(cls, email: str, client_ip: str | None) -> None:
        hour_ago = datetime.now(timezone.utc) - _SIGNUP_FLOOD_WINDOW
        email_norm = (email or '').strip().lower()

        pending_recent = cls._with_tenant_bypass(
            lambda: db.session.execute(select(Tenant).filter(
                Tenant.status == TenantStatus.PENDING,
                Tenant.created_at >= hour_ago,
            )).scalars().all()
        )
        email_count = sum(1 for t in pending_recent if (t.contact_email or '').lower() == email_norm)
        if email_count >= _SIGNUP_FLOOD_EMAIL_LIMIT:
            raise SaasRegistrationError('signup_flood_email')

        if client_ip:
            ip_count = sum(
                1 for t in pending_recent
                if (t.settings or {}).get('signup_ip') == client_ip
            )
            if ip_count >= _SIGNUP_FLOOD_IP_LIMIT:
                raise SaasRegistrationError('signup_flood_ip')

    @classmethod
    def _normalize_slug(cls, slug: str) -> str:
        value = (slug or '').strip().lower()
        if not value or not _SLUG_RE.match(value):
            raise SaasRegistrationError('invalid_slug')
        if db.session.execute(select(Tenant).filter_by(slug=value)).scalars().first():
            raise SaasRegistrationError('slug_taken')
        return value

    @classmethod
    def resolve_default_package_version_id(cls) -> int:
        env_val = os.environ.get('SAAS_DEFAULT_PACKAGE_VERSION_ID', '').strip()
        if env_val:
            return int(env_val)

        row = db.session.execute(select(PackageVersion).join(PackageVersionAvailability)
            .filter(PackageVersionAvailability.availability_status == PackageVersionAvailabilityStatus.AVAILABLE)
            .order_by(PackageVersion.id.asc())).scalars().first()
        if not row:
            raise SaasRegistrationError('no_default_package')
        return row.id

    @classmethod
    def _payment_required_at_signup(cls, package_version_id: int) -> bool:
        if os.environ.get('SAAS_REQUIRE_PAYMENT_AT_SIGNUP', '').strip().lower() in ('1', 'true', 'yes'):
            return True
        version = db.session.get(PackageVersion, package_version_id)  # global reference table - no tenant scope
        if version is None:
            return False
        return not (version.trial_days and version.trial_days > 0)

    @classmethod
    def _maybe_create_checkout(
        cls,
        tenant: Tenant,
        package_version_id: int,
        billing_type: str,
    ) -> Optional[str]:
        if not os.environ.get('STRIPE_SECRET_KEY', '').strip():
            return None
        try:
            from services.stripe_billing_service import StripeBillingService

            base = os.environ.get('SAAS_CHECKOUT_BASE_URL', '').strip().rstrip('/')
            if not base and has_request_context():
                from flask import request
                base = request.host_url.rstrip('/')
            if not base:
                base = 'http://localhost:5000'
            result = StripeBillingService.create_checkout_session(
                tenant.id,
                package_version_id,
                billing_type,
                success_url=f'{base}/auth/login?tenant_slug={tenant.slug}&payment=success',
                cancel_url=f'{base}/saas/signup?payment=cancelled',
            )
            return result.get('url')
        except Exception as exc:
            logger.warning('Checkout session creation failed tenant=%s: %s', tenant.id, exc)
            return None

    @classmethod
    def register_organization(
        cls,
        *,
        slug: str,
        name: str,
        contact_email: str,
        admin_username: str,
        admin_password: str,
        admin_full_name: str,
        package_version_id: Optional[int] = None,
        billing_type: str = 'monthly',
        product_profile_code: Optional[str] = None,
        honeypot: str | None = None,
        captcha_token: str | None = None,
        client_ip: str | None = None,
    ) -> RegistrationResult:
        cls._validate_bot_fields(honeypot)
        cls._verify_captcha(captcha_token)
        email = (contact_email or '').strip().lower()
        cls._check_signup_flood(email, client_ip)

        slug = cls._normalize_slug(slug)
        username = (admin_username or '').strip().lower()
        if not all([name, email, username, admin_password, admin_full_name]):
            raise SaasRegistrationError('missing_required_fields')
        if len(admin_password) < 8:
            raise SaasRegistrationError('weak_password')

        pkg_id = package_version_id or cls.resolve_default_package_version_id()
        payment_required = cls._payment_required_at_signup(pkg_id)

        try:
            tenant = TenantProvisioningService.provision_tenant(
                slug=slug,
                name=name.strip(),
                contact_email=email,
                package_version_id=pkg_id,
                billing_type=billing_type,
                product_profile_code=product_profile_code,
            )
        except ProvisioningError as exc:
            raise SaasRegistrationError(str(exc)) from exc

        if client_ip:
            tenant.settings = {**(tenant.settings or {}), 'signup_ip': client_ip}
            db.session.add(tenant)

        checkout_url: Optional[str] = None
        if payment_required:
            tenant.status = TenantStatus.PENDING
            db.session.add(tenant)
            db.session.flush()
            checkout_url = cls._maybe_create_checkout(tenant, pkg_id, billing_type)

        def _check_user_uniqueness_within_tenant():
            if db.session.execute(select(User).filter_by(username=username, tenant_id=tenant.id)).scalars().first():
                raise SaasRegistrationError('username_taken')
            if db.session.execute(select(User).filter_by(email=email, tenant_id=tenant.id)).scalars().first():
                raise SaasRegistrationError('email_taken')

        cls._with_tenant_bypass(_check_user_uniqueness_within_tenant)

        admin = User(
            username=username,
            email=email,
            full_name=admin_full_name.strip(),
            role=cls.DEFAULT_ADMIN_ROLE,
            is_active=True,
            tenant_id=tenant.id,
        )
        admin.set_password(admin_password)
        db.session.add(admin)
        safe_commit(db.session, error_message="Failed to save admin user", reraise=True)

        # Ticket 10: platform audit trail for tenant creation
        try:
            ip = client_ip or (request.remote_addr if has_request_context() else None)
            ua = request.headers.get('User-Agent') if has_request_context() else None
        except Exception:
            ip = None
            ua = None
        db.session.add(PlatformAuditLog(
            action='SAAS_SIGNUP',
            entity_type='tenant',
            entity_id=tenant.id,
            details=json.dumps({
                'slug': slug,
                'name': name.strip(),
                'admin_username': username,
                'admin_role': cls.DEFAULT_ADMIN_ROLE,
                'pending_payment': payment_required,
                'package_version_id': pkg_id,
                'billing_type': billing_type,
            }, ensure_ascii=False),
            ip_address=ip,
            user_agent=ua,
        ))
        safe_commit(db.session, error_message="Failed to save audit log", reraise=True)

        logger.info(
            'SaaS registration complete tenant_id=%s slug=%s admin=%s pending_payment=%s',
            tenant.id, slug, username, payment_required,
        )
        return RegistrationResult(tenant=tenant, admin=admin, checkout_url=checkout_url)
