"""Tests for UX1-002E: Emergency Workspace dashboard."""

import pytest

from app.extensions import db
from models.user import User
from sqlalchemy import select, delete


@pytest.fixture(scope='function')
def emergency_user(app, test_tenant):
    u = db.session.execute(select(User).filter_by(username='emergency_test_ux1')).scalars().first()
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
        db.session.execute(delete(LoginAttempt).filter_by(user_id=u.id))
    except Exception as e:
        db.session.rollback()


@pytest.fixture(scope='function')
def emergency_auth_client(app, client, emergency_user, test_tenant):
    from tests.tenant_context import login_test_client

    login_test_client(client, emergency_user, test_tenant, 'test123')
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
