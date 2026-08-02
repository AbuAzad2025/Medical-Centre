"""Tests for background jobs and tenant context fail-closed (Ticket 5)."""

import pytest

from app.core.tenant.models import Tenant
from app.shared.tenant_filter import TenantIsolationError
from app_factory import db as _db
from models.patient import Patient
from models.user import User
from models.visit import Visit


class TestAutoAssignFailClosed:
    def test_tenant_scoped_record_without_context_raises(self, app, test_tenant):
        """Creating a tenant-scoped record without g.tenant_id must raise."""
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        with app.test_request_context():
            from flask import g

            g.tenant_id = None
            v = Visit(patient_id=p.id, status='OPEN')
            _db.session.add(v)
            with pytest.raises(TenantIsolationError):
                _db.session.flush()
            _db.session.rollback()

    def test_global_model_without_context_allowed(self, app, test_tenant):
        """Global models (e.g., Tenant) can be created without tenant context."""
        with app.test_request_context():
            from flask import g

            g.tenant_id = None
            t = Tenant(
                name='Global Test Tenant',
                slug='global-test-t5',
                contact_email='global@test.local',
                status='active',
            )
            _db.session.add(t)
            _db.session.flush()
            _db.session.rollback()

    def test_tenant_scoped_record_with_context_succeeds(self, app, test_tenant):
        """Creating a tenant-scoped record with g.tenant_id set succeeds."""
        tenant_id = test_tenant.id
        p = Patient(first_name='ت', last_name='ت')
        _db.session.add(p)
        _db.session.commit()

        with app.test_request_context():
            from flask import g

            g.tenant_id = tenant_id
            v = Visit(patient_id=p.id, status='OPEN')
            _db.session.add(v)
            _db.session.flush()
            assert v.tenant_id == tenant_id
            _db.session.rollback()


class TestForEachTenantLifecycle:
    def test_expire_trials_runs_inside_tenant_context(self, app, test_tenant):
        """expire_trials must run inside for_each_tenant so SubscriptionLine is filtered."""
        from app.core.saas.lifecycle import TenantProvisioningService
        from services.tenant_job_runner import for_each_tenant

        results = []

        def _task(tenant_id):
            # Inside the context, g.tenant_id should be set
            from flask import g

            results.append(g.tenant_id)
            # expire_trials should not raise TenantContextError because
            # g.tenant_id is bound by for_each_tenant
            TenantProvisioningService.expire_trials()

        for_each_tenant(app, _task)
        assert test_tenant.id in results

    def test_purge_cancelled_tenants_runs_without_tenant_context(self, app, test_tenant):
        """purge_cancelled_tenants queries Tenant (global model) and works without context."""
        from app.core.saas.lifecycle import TenantProvisioningService

        with app.test_request_context():
            from flask import g

            g.tenant_id = None
            count = TenantProvisioningService.purge_cancelled_tenants()
            # Should not raise; just returns 0 because no cancelled tenants in test
            assert count >= 0


class TestGlobalModelAllowlist:
    def test_tenant_model_is_global(self, app, test_tenant):
        """Tenant itself is not tenant-scoped and can be created without context."""
        from app.core.tenant.models import Tenant
        from app.shared.tenant_filter import _skip_table

        assert _skip_table(Tenant) is True

    def test_visit_model_is_tenant_scoped(self, app, test_tenant):
        """Visit is tenant-scoped and requires context."""
        from app.shared.tenant_filter import _skip_table
        from models.visit import Visit

        assert _skip_table(Visit) is False

    def test_user_model_is_tenant_scoped(self, app, test_tenant):
        """User is tenant-scoped and requires context."""
        from app.shared.tenant_filter import _skip_table

        assert _skip_table(User) is False


class TestPurgeCancelledTenantsContract:
    """Verify purge_cancelled_tenants contract and global-model allowlist."""

    def test_purge_uses_only_global_models(self, app, test_tenant):
        """purge_cancelled_tenants must only touch global models or explicit tenant_id."""
        from app.core.saas.lifecycle import TenantProvisioningService
        from app.core.tenant.models import PlatformAuditLog, Tenant, TenantSubscriptionHistory
        from app.shared.tenant_filter import _skip_table

        # Verify global models are in allowlist
        assert _skip_table(Tenant) is True
        assert _skip_table(PlatformAuditLog) is True

        # TenantSubscriptionHistory is tenant-scoped, NOT in allowlist
        assert _skip_table(TenantSubscriptionHistory) is False

        # purge_cancelled_tenants should work without context (uses global models only)
        with app.test_request_context():
            from flask import g

            g.tenant_id = None
            count = TenantProvisioningService.purge_cancelled_tenants()
            assert count >= 0

    def test_purge_does_not_create_tenant_scoped_without_explicit_tenant_id(self, app, test_tenant):
        """purge_cancelled_tenants must not create tenant-scoped records without explicit tenant_id."""
        from app.core.saas.lifecycle import TenantProvisioningService

        with app.test_request_context():
            from flask import g

            g.tenant_id = None
            # Should not raise TenantIsolationError
            count = TenantProvisioningService.purge_cancelled_tenants()
            # No tenant-scoped records should be created without explicit tenant_id
            # (if any were, auto_assign_tenant would have raised)
            assert count >= 0

    def test_allowlist_contains_expected_global_models(self, app, test_tenant):
        """Global-model allowlist must contain all expected platform-global tables."""
        from app.core.tenant.models import PlatformAuditLog, Tenant
        from app.shared.tenant_filter import _skip_table
        from models.patient import Patient
        from models.permissions import Permission, Role
        from models.visit import Visit

        # Platform core models are global
        assert _skip_table(Tenant) is True
        assert _skip_table(PlatformAuditLog) is True
        assert _skip_table(Role) is True
        assert _skip_table(Permission) is True

        # Tenant-scoped models must NOT be in allowlist
        assert _skip_table(Visit) is False
        assert _skip_table(Patient) is False
        assert _skip_table(User) is False
