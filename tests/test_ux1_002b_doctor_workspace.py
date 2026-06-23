"""Tests for UX1-002B: Doctor Workspace dashboard."""

import pytest

from app.extensions import db
from models.user import User


@pytest.fixture(scope='function')
def doctor_user(app, test_tenant):
    u = User.query.filter_by(username='doctor_test_ux1').first()
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
        db.session.query(LoginAttempt).filter_by(user_id=u.id).delete()
    except Exception:
        db.session.rollback()


@pytest.fixture(scope='function')
def doctor_auth_client(app, client, doctor_user, test_tenant):
    from app.core.rate_limiter import _shared_store
    _shared_store.clear()
    resp = client.post('/auth/login', data={
        'username': 'doctor_test_ux1',
        'password': 'test123',
        'tenant_slug': test_tenant.slug,
    }, follow_redirects=True)
    assert resp.status_code == 200
    return client


class TestDoctorWorkspace:
    def test_dashboard_renders_with_queue_appointments_orders(self, doctor_auth_client):
        resp = doctor_auth_client.get('/doctor/dashboard')
        text = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert 'لوحة تحكم الأطباء' in text
        assert 'قائمة الانتظار' in text
        assert 'مواعيدي اليوم' in text
        assert 'طلبات المختبر المعلّقة' in text
        assert 'طلبات الأشعة المعلّقة' in text
