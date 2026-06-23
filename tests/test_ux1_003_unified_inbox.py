"""Tests for UX1-003: Unified Work Inbox."""

import pytest

from app.extensions import db
from models.user import User


@pytest.fixture(scope='function')
def staff_user(app, test_tenant):
    u = User.query.filter_by(username='staff_inbox_test').first()
    if not u:
        u = User(
            username='staff_inbox_test',
            email='staff_inbox@test.local',
            full_name='موظف صندوق عمل',
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
def inbox_auth_client(app, client, staff_user, test_tenant):
    from app.core.rate_limiter import _shared_store
    _shared_store.clear()
    resp = client.post('/auth/login', data={
        'username': 'staff_inbox_test',
        'password': 'test123',
        'tenant_slug': test_tenant.slug,
    }, follow_redirects=True)
    assert resp.status_code == 200
    return client


class TestUnifiedInbox:
    def test_inbox_renders_for_authenticated_user(self, inbox_auth_client):
        resp = inbox_auth_client.get('/inbox')
        text = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert 'صندوق العمل الموحد' in text

    def test_inbox_requires_login(self, app, client):
        resp = client.get('/inbox', follow_redirects=False)
        assert resp.status_code == 302
