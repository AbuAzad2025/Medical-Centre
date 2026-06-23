"""Tests for UX1-002E: Emergency Workspace dashboard."""

import pytest

from app.extensions import db
from models.user import User


@pytest.fixture(scope='function')
def emergency_user(app, test_tenant):
    u = User.query.filter_by(username='emergency_test_ux1').first()
    if not u:
        u = User(
            username='emergency_test_ux1',
            email='emergency_ux1@test.local',
            full_name='مسعف اختبار',
            role='emergency',
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
def emergency_auth_client(app, client, emergency_user, test_tenant):
    from app.core.rate_limiter import _shared_store
    _shared_store.clear()
    resp = client.post('/auth/login', data={
        'username': 'emergency_test_ux1',
        'password': 'test123',
        'tenant_slug': test_tenant.slug,
    }, follow_redirects=True)
    assert resp.status_code == 200
    return client


class TestEmergencyWorkspace:
    def test_dashboard_renders_with_stats_and_queue(self, emergency_auth_client):
        resp = emergency_auth_client.get('/emergency/dashboard')
        text = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert 'لوحة تحكم الطوارئ' in text
        assert 'الحالات النشطة' in text
        assert 'حالات حرجة' in text
        assert 'قائمة الانتظار' in text
