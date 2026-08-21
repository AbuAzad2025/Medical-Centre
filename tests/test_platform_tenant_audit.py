"""
Ticket 10: Audited platform tenant assumption
- SaaS registration creates PlatformAuditLog entry for tenant creation
- Log captures action=CREATE_TENANT, entity_type=tenant, tenant details
"""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.core.saas.models import (
    Package,
    PackageVersion,
    PackageVersionAvailability,
    PackageVersionAvailabilityStatus,
    PackageVersionPricing,
)
from app.core.tenant.models import PlatformAuditLog
from app_factory import db as _db
from services.saas_registration_service import SaasRegistrationService


def _seed_default_package_version() -> int:
    """Seed an active package version so resolve_default_package_version_id()
    finds a candidate (platform bootstrap is skipped under tests)."""
    pkg = Package(
        name='Starter',
        slug=f'starter-{uuid.uuid4().hex[:8]}',
        category='bundle',
        is_active=True,
    )
    _db.session.add(pkg)
    _db.session.flush()
    version = PackageVersion(
        package_id=pkg.id,
        version='1.0.0',
        trial_days=7,
        published_at=datetime.now(UTC),
    )
    _db.session.add(version)
    _db.session.flush()
    _db.session.add(
        PackageVersionPricing(
            package_version_id=version.id,
            billing_type='monthly',
            price=100,
            setup_fee=0,
            currency='SAR',
        )
    )
    _db.session.add(
        PackageVersionAvailability(
            package_version_id=version.id,
            availability_status=PackageVersionAvailabilityStatus.AVAILABLE,
            effective_from=datetime.now(UTC),
        )
    )
    _db.session.commit()
    return version.id


@pytest.mark.usefixtures('app')
class TestPlatformTenantAudit:
    def test_registration_creates_platform_audit_log(self, app):
        with app.app_context():
            _seed_default_package_version()
            slug = 'audit-tenant-' + uuid.uuid4().hex[:6]
            result = SaasRegistrationService.register_organization(
                slug=slug,
                name='Audit Tenant',
                contact_email='audit-' + uuid.uuid4().hex[:6] + '@example.com',
                admin_username='admin_' + uuid.uuid4().hex[:6],
                admin_password='SecurePass123!',
                admin_full_name='Audit Admin',
            )
            assert result.tenant is not None
            assert result.admin is not None

            # Verify platform audit log was created for SaaS signup
            log = _db.session.execute(
                select(PlatformAuditLog).filter_by(
                    action='SAAS_SIGNUP',
                    entity_type='tenant',
                    entity_id=result.tenant.id,
                )
            ).scalar()
            assert log is not None
            assert log.details is not None
            assert slug in log.details
            assert 'Audit Tenant' in log.details
            assert 'admin_' in log.details

    def test_registration_audit_log_includes_ip_when_available(self, app):
        with app.app_context():
            _seed_default_package_version()
            slug = 'audit-ip-' + uuid.uuid4().hex[:6]
            result = SaasRegistrationService.register_organization(
                slug=slug,
                name='Audit IP Tenant',
                contact_email='ip-' + uuid.uuid4().hex[:6] + '@example.com',
                admin_username='admin_' + uuid.uuid4().hex[:6],
                admin_password='SecurePass123!',
                admin_full_name='IP Admin',
                client_ip='192.168.1.100',
            )
            log = _db.session.execute(
                select(PlatformAuditLog).filter_by(
                    action='SAAS_SIGNUP',
                    entity_id=result.tenant.id,
                )
            ).scalar()
            assert log is not None
            assert log.ip_address == '192.168.1.100'
