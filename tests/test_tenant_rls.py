"""Integration tests for database-level tenant isolation (fail-closed behavior)."""

import uuid
from datetime import datetime, timezone

import pytest
from flask import g

from app.extensions import db
from app.core.tenant.models import Tenant, TenantStatus
from app.shared.tenant_filter import TenantIsolationError
from models.patient import Patient


@pytest.fixture
def tenant_a(app):
    t = Tenant(
        slug=f'tenant-a-{uuid.uuid4().hex[:6]}',
        name='Tenant A',
        contact_email='a@test.local',
        status=TenantStatus.ACTIVE,
        product_profile_code='standalone_clinic',
    )
    db.session.add(t)
    db.session.commit()
    return t


@pytest.fixture
def tenant_b(app):
    t = Tenant(
        slug=f'tenant-b-{uuid.uuid4().hex[:6]}',
        name='Tenant B',
        contact_email='b@test.local',
        status=TenantStatus.ACTIVE,
        product_profile_code='standalone_clinic',
    )
    db.session.add(t)
    db.session.commit()
    return t


class TestFailClosedTenantIsolation:
    def test_saas_mode_no_tenant_raises_isolation_error(self, app, tenant_a):
        """In SaaS mode, querying a tenant-scoped model without g.tenant_id raises."""
        with app.test_request_context():
            app.config['ENABLE_SAAS_MODE'] = True
            g.tenant_id = None
            g._tenant_filter_bypass = False
            with pytest.raises(TenantIsolationError):
                Patient.query.all()

    def test_saas_mode_with_tenant_succeeds(self, app, tenant_a):
        """In SaaS mode with tenant context, queries execute normally."""
        with app.test_request_context():
            app.config['ENABLE_SAAS_MODE'] = True
            g.tenant_id = tenant_a.id
            result = Patient.query.all()
            assert isinstance(result, list)

    def test_cross_tenant_data_invisible(self, app, tenant_a, tenant_b):
        """Tenant A cannot see Tenant B's data."""
        p = Patient(
            tenant_id=tenant_b.id,
            first_name='Secret',
            last_name='Patient',
            gender='male',
            phone='0000000000',
        )
        db.session.add(p)
        db.session.commit()
        patient_id = p.id

        with app.test_request_context():
            app.config['ENABLE_SAAS_MODE'] = True
            g.tenant_id = tenant_a.id
            found = Patient.query.filter_by(id=patient_id).first()
            assert found is None

    def test_bypass_flag_allows_global_query(self, app, tenant_a):
        """Explicit bypass flag allows queries without tenant context."""
        with app.test_request_context():
            app.config['ENABLE_SAAS_MODE'] = True
            g.tenant_id = None
            g._tenant_filter_bypass = True
            result = Patient.query.all()
            assert isinstance(result, list)

    def test_non_saas_mode_allows_global_query(self, app, tenant_a):
        """In non-SaaS mode, queries without tenant context work normally."""
        with app.test_request_context():
            app.config['ENABLE_SAAS_MODE'] = False
            g.tenant_id = None
            result = Patient.query.all()
            assert isinstance(result, list)
