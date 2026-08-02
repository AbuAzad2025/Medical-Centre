"""Integration tests for database-level tenant isolation (fail-closed behavior)."""

import pytest
from flask import g
from sqlalchemy import select

from app.core.tenant.models import Tenant
from app.extensions import db
from app.shared.tenant_filter import TenantIsolationError
from models.patient import Patient


@pytest.fixture
def tenant_a(app):
    from tests.tenant_context import DEFAULT_TEST_TENANT_SLUG

    t = (
        db.session.execute(select(Tenant).filter_by(slug=DEFAULT_TEST_TENANT_SLUG))
        .scalars()
        .first()
    )
    if t is None:
        raise RuntimeError(
            f'Default tenant "{DEFAULT_TEST_TENANT_SLUG}" not found — bootstrap first'
        )
    return t


@pytest.fixture
def tenant_b(app):
    import uuid

    from flask import g

    from tests.tenant_context import DEFAULT_TEST_TENANT_SLUG

    prev = g.get('_tenant_filter_bypass', False)
    g._tenant_filter_bypass = True
    try:
        t = db.session.execute(
            select(Tenant).filter(Tenant.slug != DEFAULT_TEST_TENANT_SLUG)
        ).scalar()
        if t is None:
            t = Tenant(
                slug=f'tenant-b-{uuid.uuid4().hex[:8]}',
                name='Tenant B',
                contact_email='tenantb@test.local',
                status='active',
                product_profile_code='multi_department_center',
            )
            db.session.add(t)
            db.session.commit()
    finally:
        if prev:
            g._tenant_filter_bypass = True
        else:
            g.pop('_tenant_filter_bypass', None)
    return t


@pytest.mark.no_tenant_context
class TestFailClosedTenantIsolation:
    def test_saas_mode_no_tenant_raises_isolation_error(self, app, tenant_a):
        """In SaaS mode, querying a tenant-scoped model without g.tenant_id raises."""
        with app.test_request_context():
            app.config['ENABLE_SAAS_MODE'] = True
            g.tenant_id = None
            g._tenant_filter_bypass = False
            with pytest.raises(TenantIsolationError):
                db.session.execute(select(Patient)).scalars().all()

    def test_saas_mode_with_tenant_succeeds(self, app, tenant_a):
        """In SaaS mode with tenant context, queries execute normally."""
        with app.test_request_context():
            app.config['ENABLE_SAAS_MODE'] = True
            g.tenant_id = tenant_a.id
            result = db.session.execute(select(Patient)).scalars().all()
            assert isinstance(result, list)

    def test_cross_tenant_data_invisible(self, app, tenant_a, tenant_b):
        """Tenant A cannot see Tenant B's data."""
        from tests.tenant_context import bind_tenant_on_g

        with app.test_request_context():
            app.config['ENABLE_SAAS_MODE'] = True
            bind_tenant_on_g(tenant_b, db_session=db.session)
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
            bind_tenant_on_g(tenant_a, db_session=db.session)
            found = db.session.execute(select(Patient).filter_by(id=patient_id)).scalars().first()
            assert found is None

    def test_bypass_flag_allows_global_query(self, app, tenant_a):
        """Explicit bypass flag allows queries without tenant context."""
        with app.test_request_context():
            app.config['ENABLE_SAAS_MODE'] = True
            g.tenant_id = None
            g._tenant_filter_bypass = True
            result = db.session.execute(select(Patient)).scalars().all()
            assert isinstance(result, list)

    def test_non_saas_mode_allows_global_query(self, app, tenant_a):
        """In non-SaaS mode, queries without tenant context work normally."""
        with app.test_request_context():
            app.config['ENABLE_SAAS_MODE'] = False
            g.tenant_id = None
            result = db.session.execute(select(Patient)).scalars().all()
            assert isinstance(result, list)
