"""Tests for UX1-004: Patient 360 Timeline."""

import pytest

from app.extensions import db
from models.user import User
from models.patient import Patient


@pytest.fixture(scope='function')
def doctor_user(app, test_tenant):
    u = User.query.filter_by(username='doctor_timeline_test').first()
    if not u:
        u = User(
            username='doctor_timeline_test',
            email='doctor_timeline@test.local',
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
def sample_patient(app, test_tenant, monkeypatch):
    # Avoid bundle-limit failures caused by accumulated test data.
    monkeypatch.setattr(
        'app.shared.tenant_filter._check_bundle_limits_on_create',
        lambda instance, tenant_id: None,
    )
    p = Patient.query.filter_by(national_id='TIMELINE-001').first()
    if not p:
        p = Patient(
            first_name='Timeline',
            last_name='Patient',
            first_name_ar='مريض',
            last_name_ar='الخط الزمني',
            national_id='TIMELINE-001',
            phone='0599000001',
            tenant_id=test_tenant.id,
        )
        db.session.add(p)
        db.session.commit()
    yield p


@pytest.fixture(scope='function')
def timeline_auth_client(app, client, doctor_user, test_tenant):
    from app.core.rate_limiter import _shared_store
    _shared_store.clear()
    resp = client.post('/auth/login', data={
        'username': 'doctor_timeline_test',
        'password': 'test123',
        'tenant_slug': test_tenant.slug,
    }, follow_redirects=True)
    assert resp.status_code == 200
    return client


class TestPatientTimeline:
    def test_timeline_renders(self, timeline_auth_client, sample_patient):
        resp = timeline_auth_client.get(f'/doctor/patient-timeline/{sample_patient.id}')
        text = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert 'الخط الزمني للمريض' in text
        assert sample_patient.full_name in text
