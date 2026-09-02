"""Tests for UX1-002B: Doctor Workspace dashboard."""

import pytest
from sqlalchemy import delete, select

from app.extensions import db
from models.user import User


@pytest.fixture(scope='function')
def doctor_user(app, test_tenant):
    u = db.session.execute(select(User).filter_by(username='doctor_test_ux1')).scalars().first()
    if not u:
        u = User(
            username='doctor_test_ux1',
            email='doctor_ux1@test.local',
            full_name='طبيب اختبار',
            role='doctor',
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
def doctor_auth_client(app, client, doctor_user, test_tenant):
    from tests.tenant_context import login_test_client

    login_test_client(client, doctor_user, test_tenant, 'test123')
    return client


class TestDoctorWorkspace:
    def test_dashboard_renders_with_queue_appointments_orders(self, doctor_auth_client):
        resp = doctor_auth_client.get('/doctor/dashboard')
        text = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert 'لوحة تحكم الأطباء' in text
