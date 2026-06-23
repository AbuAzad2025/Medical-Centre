"""Tests for S0-004: Combined Access Contract (Entitlement + Authorization)."""

from datetime import date, datetime, timedelta, timezone

import pytest

from app.extensions import db
from app.core.saas.exceptions import EntitlementDeniedError
from app.core.saas.resolver import EntitlementResolver
from app.core.saas.decorators import require_entitlement
from app.core.saas.models import TenantEntitlement
from app.core.tenant.models import PlatformAuditLog, Tenant, TenantStatus
from models.user import User


@pytest.fixture(scope='function')
def access_tenant(app):
    t = Tenant(
        slug=f"access-{datetime.now(timezone.utc).timestamp()}",
        name='Access Test Tenant',
        contact_email='access@test.local',
        status=TenantStatus.ACTIVE,
        product_profile_code='standalone_clinic',
    )
    db.session.add(t)
    db.session.commit()
    yield t
    db.session.delete(t)
    db.session.commit()


@pytest.fixture(scope='function')
def access_user(app, access_tenant):
    u = User(
        username=f"access_user_{datetime.now(timezone.utc).timestamp()}",
        email='access-user@test.local',
        full_name='Access User',
        role='admin',
        is_active=True,
        tenant_id=access_tenant.id,
    )
    u.set_password('test123')
    db.session.add(u)
    db.session.commit()
    yield u
    db.session.delete(u)
    db.session.commit()


class TestEntitlementResolver:
    def test_active_tenant_without_projection_is_not_entitled(self, access_tenant):
        assert EntitlementResolver.is_entitled(access_tenant.id, "lab.order") is False

    def test_entitled_when_projection_active(self, access_tenant):
        te = TenantEntitlement(
            tenant_id=access_tenant.id,
            capability_key="lab.order",
            module_name="lab",
            effective_from=datetime.now(timezone.utc) - timedelta(hours=1),
            is_effective=True,
            calculated_at=datetime.now(timezone.utc),
            calculation_version=1,
        )
        db.session.add(te)
        db.session.commit()

        assert EntitlementResolver.is_entitled(access_tenant.id, "lab.order") is True

    def test_inactive_tenant_denied(self, access_tenant):
        access_tenant.status = TenantStatus.SUSPENDED
        db.session.commit()

        te = TenantEntitlement(
            tenant_id=access_tenant.id,
            capability_key="lab.order",
            module_name="lab",
            effective_from=datetime.now(timezone.utc) - timedelta(hours=1),
            is_effective=True,
            calculated_at=datetime.now(timezone.utc),
            calculation_version=1,
        )
        db.session.add(te)
        db.session.commit()

        assert EntitlementResolver.is_entitled(access_tenant.id, "lab.order") is False

    def test_expired_subscription_denied(self, access_tenant):
        access_tenant.subscription_end = date.today() - timedelta(days=5)
        db.session.commit()

        te = TenantEntitlement(
            tenant_id=access_tenant.id,
            capability_key="lab.order",
            module_name="lab",
            effective_from=datetime.now(timezone.utc) - timedelta(hours=1),
            is_effective=True,
            calculated_at=datetime.now(timezone.utc),
            calculation_version=1,
        )
        db.session.add(te)
        db.session.commit()

        assert EntitlementResolver.is_entitled(access_tenant.id, "lab.order") is False

    def test_assert_entitled_raises(self, access_tenant):
        with pytest.raises(EntitlementDeniedError):
            EntitlementResolver.assert_entitled(access_tenant.id, "lab.order")

    def test_audit_log_deduplication_per_request(self, access_tenant, client):
        EntitlementResolver.is_entitled(access_tenant.id, "lab.order")
        EntitlementResolver.is_entitled(access_tenant.id, "lab.order")

        logs = PlatformAuditLog.query.filter_by(
            tenant_id=access_tenant.id, action="ENTITLEMENT_DENIED"
        ).all()
        assert len(logs) == 1
        assert "lab.order" in (logs[0].details or "")


class TestRequireEntitlementDecorator:
    def test_route_blocks_without_entitlement(self, app, access_tenant):
        from flask import g
        from werkzeug.exceptions import Forbidden

        @require_entitlement("lab.order")
        def blocked_view():
            return "ok", 200

        with app.test_request_context():
            g.current_tenant = access_tenant
            with pytest.raises(Forbidden):
                blocked_view()

    def test_route_allows_with_entitlement(self, app, access_tenant):
        from flask import g

        te = TenantEntitlement(
            tenant_id=access_tenant.id,
            capability_key="lab.order",
            module_name="lab",
            effective_from=datetime.now(timezone.utc) - timedelta(hours=1),
            is_effective=True,
            calculated_at=datetime.now(timezone.utc),
            calculation_version=1,
        )
        db.session.add(te)
        db.session.commit()

        @require_entitlement("lab.order")
        def allowed_view():
            return "ok", 200

        with app.test_request_context():
            g.current_tenant = access_tenant
            result = allowed_view()
            assert result == ("ok", 200)
