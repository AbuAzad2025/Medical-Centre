"""SaaS self-service registration integration tests."""

import uuid

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
from datetime import datetime, timezone
from models.user import User
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


class TestSaasRegistrationService:
    def test_register_creates_tenant_and_admin(self, app):
        version = _seed_package_version()
        slug = f'clinic-{uuid.uuid4().hex[:6]}'
        with tenant_test_context(app, bypass=True):
            tenant, admin = SaasRegistrationService.register_organization(
                slug=slug,
                name='عيادة الاختبار',
                contact_email=f'{slug}@example.com',
                admin_username=f'admin_{slug}',
                admin_password='securepass1',
                admin_full_name='مدير العيادة',
                package_version_id=version.id,
            )
        assert tenant.slug == slug
        assert admin.tenant_id == tenant.id
        assert admin.role == 'manager'
        with tenant_test_context(app, tenant):
            assert User.query.filter_by(tenant_id=tenant.id).count() == 1

    def test_duplicate_slug_rejected(self, app):
        version = _seed_package_version()
        slug = f'dup-{uuid.uuid4().hex[:6]}'
        with tenant_test_context(app, bypass=True):
            SaasRegistrationService.register_organization(
                slug=slug,
                name='A',
                contact_email=f'a-{slug}@example.com',
                admin_username=f'u1_{slug}',
                admin_password='securepass1',
                admin_full_name='A',
                package_version_id=version.id,
            )
            with pytest.raises(SaasRegistrationError, match='slug_taken'):
                SaasRegistrationService.register_organization(
                    slug=slug,
                    name='B',
                    contact_email=f'b-{slug}@example.com',
                    admin_username=f'u2_{slug}',
                    admin_password='securepass1',
                    admin_full_name='B',
                    package_version_id=version.id,
                )


class TestSaasRegistrationRoute:
    def test_public_register_endpoint(self, client, app):
        version = _seed_package_version()
        slug = f'api-{uuid.uuid4().hex[:6]}'
        resp = client.post('/api/saas/register', json={
            'slug': slug,
            'name': 'مركز صحي',
            'contact_email': f'{slug}@clinic.test',
            'admin_username': f'owner_{slug}',
            'admin_password': 'securepass1',
            'admin_full_name': 'المالك',
            'package_version_id': version.id,
        })
        assert resp.status_code == 201
        body = resp.get_json()
        assert body['tenant']['slug'] == slug
        tenant = Tenant.query.filter_by(slug=slug).first()
        assert tenant is not None
        with tenant_test_context(app, tenant):
            assert User.query.filter_by(tenant_id=tenant.id).count() == 1
