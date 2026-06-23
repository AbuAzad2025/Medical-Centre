"""Tests for UX1-002A: Reception and Manager Workspace dashboards."""

import pytest

from app.extensions import db
from models.user import User


@pytest.fixture(scope='function')
def reception_user(app, test_tenant):
    u = User.query.filter_by(username='reception_test_ux1').first()
    if not u:
        u = User(
            username='reception_test_ux1',
            email='reception_ux1@test.local',
            full_name='موظف استقبال اختبار',
            role='reception',
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
def reception_auth_client(app, client, reception_user, test_tenant):
    from app.core.rate_limiter import _shared_store
    _shared_store.clear()
    resp = client.post('/auth/login', data={
        'username': 'reception_test_ux1',
        'password': 'test123',
        'tenant_slug': test_tenant.slug,
    }, follow_redirects=True)
    assert resp.status_code == 200
    return client


class TestReceptionWorkspace:
    def test_dashboard_renders_with_checkin_appointments_waitlist(self, reception_auth_client):
        resp = reception_auth_client.get('/reception/dashboard')
        text = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert 'لوحة تحكم الاستقبال' in text
        assert 'زيارات اليوم' in text
        assert 'مواعيد اليوم' in text
        assert 'الطابور النشط' in text


class TestManagerWorkspace:
    def test_dashboard_renders_with_appointments_and_approvals(self, manager_auth_client):
        resp = manager_auth_client.get('/manager/dashboard')
        text = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert 'command-center' in text or 'لوحة القيادة' in text
        assert 'تخصيص اللوحة' in text
