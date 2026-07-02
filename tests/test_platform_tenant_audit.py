"""
Ticket 10: Audited platform tenant assumption
- SaaS registration creates PlatformAuditLog entry for tenant creation
- Log captures action=CREATE_TENANT, entity_type=tenant, tenant details
"""
import pytest, uuid
from datetime import datetime, timezone
from app.core.tenant.models import Tenant, PlatformAuditLog
from app.shared.enums import TenantStatus
from services.saas_registration_service import SaasRegistrationService, SaasRegistrationError
from app_factory import db as _db


@pytest.mark.usefixtures('app')
class TestPlatformTenantAudit:
    def test_registration_creates_platform_audit_log(self, app):
        with app.app_context():
            slug = 'audit-tenant-' + uuid.uuid4().hex[:6]
            result = SaasRegistrationService.register_organization(
                slug=slug,
                name='Audit Tenant',
                contact_email='audit-'+uuid.uuid4().hex[:6]+'@example.com',
                admin_username='admin_' + uuid.uuid4().hex[:6],
                admin_password='SecurePass123!',
                admin_full_name='Audit Admin',
            )
            assert result.tenant is not None
            assert result.admin is not None

            # Verify platform audit log was created for SaaS signup
            log = PlatformAuditLog.query.filter_by(
                action='SAAS_SIGNUP',
                entity_type='tenant',
                entity_id=result.tenant.id,
            ).first()
            assert log is not None
            assert log.details is not None
            assert slug in log.details
            assert 'Audit Tenant' in log.details
            assert 'admin_' in log.details

    def test_registration_audit_log_includes_ip_when_available(self, app):
        with app.app_context():
            slug = 'audit-ip-' + uuid.uuid4().hex[:6]
            result = SaasRegistrationService.register_organization(
                slug=slug,
                name='Audit IP Tenant',
                contact_email='ip-'+uuid.uuid4().hex[:6]+'@example.com',
                admin_username='admin_' + uuid.uuid4().hex[:6],
                admin_password='SecurePass123!',
                admin_full_name='IP Admin',
                client_ip='192.168.1.100',
            )
            log = PlatformAuditLog.query.filter_by(
                action='SAAS_SIGNUP',
                entity_id=result.tenant.id,
            ).first()
            assert log is not None
            assert log.ip_address == '192.168.1.100'
