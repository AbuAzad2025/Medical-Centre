"""S0-007: Platform owner console access separation tests."""

import uuid

import pytest

from app.extensions import db
from models.user import User


@pytest.fixture(scope='function')
def tenant_admin(app, test_tenant):
    tag = uuid.uuid4().hex[:8]
    u = User(
        username=f"tadmin_{tag}",
        email=f"tadmin_{tag}@test.local",
        full_name='Tenant Admin',
        role='admin',
        is_active=True,
        tenant_id=test_tenant.id,
    )
    u.set_password('test123')
    db.session.add(u)
    db.session.commit()
    yield u
    try:
        from models.audit_trail import LoginAttempt
        db.session.query(LoginAttempt).filter_by(user_id=u.id).delete()
    except Exception:
        db.session.rollback()
    db.session.delete(u)
    db.session.commit()


class TestOwnerConsoleSecurity:
    def test_tenant_admin_blocked_from_owner_api(self, app, client, tenant_admin, test_tenant):
        from app.core.rate_limiter import _shared_store
        _shared_store.clear()
        client.post('/auth/login', data={
            'username': tenant_admin.username,
            'password': 'test123',
            'tenant_slug': test_tenant.slug,
        })
        resp = client.get('/owner/api/tenants')
        assert resp.status_code == 403

    def test_platform_owner_allowed(self, app, client, test_tenant):
        from app.core.rate_limiter import _shared_store
        u = User.query.filter_by(username='owner_sec_test').first()
        if not u:
            u = User(
                username='owner_sec_test',
                email='owner_sec@test.local',
                full_name='Platform Owner',
                role='owner',
                is_active=True,
                tenant_id=test_tenant.id,
            )
            u.set_password('test123')
            db.session.add(u)
            db.session.commit()
        _shared_store.clear()
        client.post('/auth/login', data={
            'username': 'owner_sec_test',
            'password': 'test123',
            'tenant_slug': test_tenant.slug,
        })
        resp = client.get('/owner/dashboard')
        assert resp.status_code in (200, 302)
