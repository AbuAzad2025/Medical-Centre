"""Tests for UX0-004 / UX0-005 / UX0-006 tenant-facing SaaS UI pages."""

import uuid

import pytest

from app.extensions import db
from models.user import User


@pytest.fixture(scope='function')
def superadmin_user(app, test_tenant):
    username = f"sa_test_{uuid.uuid4().hex[:8]}"
    u = User(
        username=username,
        email=f"{username}@example.com",
        full_name='Super Admin Test',
        role='super_admin',
        is_active=True,
        tenant_id=test_tenant.id,
    )
    u.set_password('sa123456')
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


@pytest.fixture(scope='function')
def logged_in_super_client(client, superadmin_user):
    resp = client.post(
        '/auth/login',
        data={'username': superadmin_user.username, 'password': 'sa123456'},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    yield client
    client.get('/auth/logout')


class TestUX0TenantUI:
    def test_subscription_status_requires_login(self, client):
        resp = client.get('/super-admin/subscription-status')
        assert resp.status_code in (302, 401, 403)

    def test_subscription_status_renders(self, logged_in_super_client):
        resp = logged_in_super_client.get('/super-admin/subscription-status')
        assert resp.status_code == 200
        assert 'حالة الاشتراك' in resp.get_data(as_text=True)

    def test_change_plan_renders(self, logged_in_super_client):
        resp = logged_in_super_client.get('/super-admin/change-plan')
        assert resp.status_code == 200
        assert 'تغيير الخطة' in resp.get_data(as_text=True)

    def test_tenant_usage_renders(self, logged_in_super_client):
        resp = logged_in_super_client.get('/super-admin/usage')
        assert resp.status_code == 200
        assert 'استخدام الموارد' in resp.get_data(as_text=True)
