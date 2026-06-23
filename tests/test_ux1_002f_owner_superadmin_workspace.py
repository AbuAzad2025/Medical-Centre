"""Tests for UX1-002F: Tenant-Admin and Platform-Owner Workspace dashboards."""

import pytest

from app.extensions import db
from models.user import User


@pytest.fixture(scope='function')
def owner_user(app, test_tenant):
    u = User.query.filter_by(username='owner_test_ux1').first()
    if not u:
        u = User(
            username='owner_test_ux1',
            email='owner_ux1@test.local',
            full_name='مالك اختبار',
            role='owner',
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


@pytest.fixture(scope='function')
def superadmin_user(app, test_tenant):
    u = User.query.filter_by(username='superadmin_test_ux1').first()
    if not u:
        u = User(
            username='superadmin_test_ux1',
            email='superadmin_ux1@test.local',
            full_name='سوبر أدمن اختبار',
            role='super_admin',
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


@pytest.fixture(scope='function')
def owner_auth_client(app, client, owner_user, test_tenant):
    from app.core.rate_limiter import _shared_store
    _shared_store.clear()
    resp = client.post('/auth/login', data={
        'username': 'owner_test_ux1',
        'password': 'test123',
        'tenant_slug': test_tenant.slug,
    }, follow_redirects=True)
    assert resp.status_code == 200
    return client


@pytest.fixture(scope='function')
def superadmin_auth_client(app, client, superadmin_user, test_tenant):
    from app.core.rate_limiter import _shared_store
    _shared_store.clear()
    resp = client.post('/auth/login', data={
        'username': 'superadmin_test_ux1',
        'password': 'test123',
        'tenant_slug': test_tenant.slug,
    }, follow_redirects=True)
    assert resp.status_code == 200
    return client


class TestOwnerWorkspace:
    def test_owner_dashboard_renders(self, owner_auth_client):
        resp = owner_auth_client.get('/owner/dashboard')
        text = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert 'لوحة تحكم المنصة' in text
        assert 'إجمالي العملاء' in text


class TestSuperAdminWorkspace:
    def test_superadmin_dashboard_renders(self, superadmin_auth_client):
        resp = superadmin_auth_client.get('/super-admin/dashboard')
        text = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert 'لوحة السوبر أدمن' in text
        assert 'إجمالي المستخدمين' in text


class TestOwnerSaaSPages:
    """Owner SaaS management pages (packages, subscriptions, provision)."""

    def test_packages_page_requires_login(self, client):
        resp = client.get('/owner/packages')
        assert resp.status_code == 302

    def test_packages_page_renders(self, owner_auth_client):
        resp = owner_auth_client.get('/owner/packages')
        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert 'Package' in text or 'اشتراك' in text or 'باقة' in text

    def test_subscriptions_page_renders(self, owner_auth_client):
        resp = owner_auth_client.get('/owner/subscriptions')
        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert 'اشتراكات' in text or 'Subscriptions' in text

    def test_provision_page_renders(self, owner_auth_client):
        resp = owner_auth_client.get('/owner/provision')
        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert 'SaaS Provisioning' in text or 'إنشاء عميل' in text
