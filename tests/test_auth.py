"""
Authentication and authorization tests.
"""
import pytest
from flask import url_for, session


class TestAuth:
    """Authentication flow tests."""

    def test_login_page_loads(self, client):
        resp = client.get('/auth/login')
        assert resp.status_code == 200
        assert 'تسجيل الدخول' in resp.data.decode('utf-8')

    def test_login_success(self, client, test_user, test_tenant):
        resp = client.post('/auth/login', data={
            'username': 'pharmacist_test',
            'password': 'test123',
            'tenant_slug': test_tenant.slug,
        })
        assert resp.status_code == 302
        assert f'/t/{test_tenant.slug}/' in resp.headers['Location']

    def test_login_wrong_password(self, client, test_user):
        resp = client.post('/auth/login', data={
            'username': 'pharmacist_test',
            'password': 'wrongpassword',
        })
        assert resp.status_code == 200
        assert 'كلمة المرور غير صحيحة' in resp.data.decode('utf-8')

    def test_login_inactive_user(self, app, client, test_user):
        test_user.is_active = False
        from app_factory import db
        db.session.commit()
        resp = client.post('/auth/login', data={
            'username': 'pharmacist_test',
            'password': 'test123',
        })
        assert resp.status_code == 200
        assert 'غير مفعل' in resp.data.decode('utf-8')
        test_user.is_active = True
        db.session.commit()

    def test_protected_route_redirects(self, app):
        # Brand-new client => empty cookie jar; autouse _clear_flask_login_state
        # clears any leaked g._login_user, so this is order-independent.
        fresh = app.test_client()
        resp = fresh.get('/medication/dashboard')
        assert resp.status_code == 302
        assert '/auth/login' in resp.headers['Location']

    def test_role_required(self, auth_client, app, test_user, test_tenant):
        """Pharmacist should access medication dashboard, but not doctor dashboard."""
        resp = auth_client.get('/medication/dashboard')
        assert resp.status_code in (200, 302)
        resp = auth_client.get('/doctor/dashboard')
        assert resp.status_code in (302, 403)

    def test_logout(self, auth_client):
        resp = auth_client.get('/auth/logout', follow_redirects=True)
        assert resp.status_code == 200
        assert 'تسجيل الدخول' in resp.data.decode('utf-8')
