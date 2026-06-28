"""Automated SaaS self-service tenant registration (S0 provisioning loop)."""
from __future__ import annotations

import logging
import os
import re
from typing import Optional, Tuple

from flask import g, has_request_context

from app.extensions import db
from app.core.saas.lifecycle import ProvisioningError, TenantProvisioningService
from app.core.saas.models import PackageVersion, PackageVersionAvailability, PackageVersionAvailabilityStatus
from app.core.tenant.models import Tenant
from models.user import User

logger = logging.getLogger(__name__)

_SLUG_RE = re.compile(r'^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$')


class SaasRegistrationError(ValueError):
    """Validation or provisioning failure for public signup."""


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
    def _normalize_slug(cls, slug: str) -> str:
        value = (slug or '').strip().lower()
        if not value or not _SLUG_RE.match(value):
            raise SaasRegistrationError('invalid_slug')
        if Tenant.query.filter_by(slug=value).first():
            raise SaasRegistrationError('slug_taken')
        return value

    @classmethod
    def resolve_default_package_version_id(cls) -> int:
        env_val = os.environ.get('SAAS_DEFAULT_PACKAGE_VERSION_ID', '').strip()
        if env_val:
            return int(env_val)

        row = (
            PackageVersion.query.join(PackageVersionAvailability)
            .filter(PackageVersionAvailability.availability_status == PackageVersionAvailabilityStatus.AVAILABLE)
            .order_by(PackageVersion.id.asc())
            .first()
        )
        if not row:
            raise SaasRegistrationError('no_default_package')
        return row.id

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
    ) -> Tuple[Tenant, User]:
        slug = cls._normalize_slug(slug)
        email = (contact_email or '').strip().lower()
        username = (admin_username or '').strip().lower()
        if not all([name, email, username, admin_password, admin_full_name]):
            raise SaasRegistrationError('missing_required_fields')
        if len(admin_password) < 8:
            raise SaasRegistrationError('weak_password')
        def _check_user_uniqueness():
            if User.query.filter_by(username=username).first():
                raise SaasRegistrationError('username_taken')
            if User.query.filter_by(email=email).first():
                raise SaasRegistrationError('email_taken')

        cls._with_tenant_bypass(_check_user_uniqueness)

        pkg_id = package_version_id or cls.resolve_default_package_version_id()

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
        db.session.commit()

        logger.info('SaaS registration complete tenant_id=%s slug=%s admin=%s', tenant.id, slug, username)
        return tenant, admin
