"""Tests for UX1-002C: Lab and Radiology Workspace dashboards."""

import pytest
from sqlalchemy import delete, select

from app.extensions import db
from models.user import User


@pytest.fixture(scope='function')
def lab_user(app, test_tenant):
    u = db.session.execute(select(User).filter_by(username='lab_test_ux1')).scalars().first()
    if not u:
        u = User(
            username='lab_test_ux1',
            email='lab_ux1@test.local',
            full_name='فني مختبر اختبار',
            role='lab',
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
    except Exception:
        db.session.rollback()


@pytest.fixture(scope='function')
def radiology_user(app, test_tenant):
    u = db.session.execute(select(User).filter_by(username='radiology_test_ux1')).scalars().first()
    if not u:
        u = User(
            username='radiology_test_ux1',
            email='radiology_ux1@test.local',
            full_name='فني أشعة اختبار',
            role='radiology',
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
    except Exception:
        db.session.rollback()


@pytest.fixture(scope='function')
def lab_auth_client(app, client, lab_user, test_tenant, monkeypatch):
    from tests.tenant_context import login_test_client

    monkeypatch.setattr(
        'app.core.saas.resolver.EntitlementResolver.is_entitled', lambda *a, **k: True
    )

    login_test_client(client, lab_user, test_tenant, 'test123')
    return client


@pytest.fixture(scope='function')
def radiology_auth_client(app, client, radiology_user, test_tenant):
    from tests.tenant_context import login_test_client

    login_test_client(client, radiology_user, test_tenant, 'test123')
    return client


class TestLabWorkspace:
    def test_dashboard_renders_with_worklist(self, lab_auth_client):
        resp = lab_auth_client.get('/lab/dashboard')
        text = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert 'قسم المختبر' in text
        assert 'آخر طلبات المختبر' in text


class TestRadiologyWorkspace:
    def test_dashboard_renders_with_requests(self, radiology_auth_client):
        resp = radiology_auth_client.get('/radiology/dashboard')
        text = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert 'قسم الأشعة' in text
