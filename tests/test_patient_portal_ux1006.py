"""Tests for UX1-006: Patient Portal and Public Booking."""

import uuid

import pytest

from app_factory import db as _db
from models.patient import Patient
from models.patient_account import PatientAccount
from models.user import User


@pytest.fixture(scope='function')
def portal_patient(app, test_tenant):
    suffix = uuid.uuid4().hex[:8]
    p = Patient(
        tenant_id=test_tenant.id,
        first_name=f'PortalPatient{suffix}',
        last_name='Test',
        phone='0500000000',
        national_id=f'ID{suffix}',
    )
    _db.session.add(p)
    _db.session.commit()
    return p


@pytest.fixture(scope='function')
def portal_user(app, test_tenant, portal_patient):
    suffix = uuid.uuid4().hex[:6]
    u = User(
        username=f'portal_{suffix}',
        email=f'portal_{suffix}@test.local',
        full_name='مريض اختبار',
        role='patient',
        is_active=True,
        tenant_id=test_tenant.id,
        phone='0500000000',
    )
    u.set_password('test123')
    _db.session.add(u)
    _db.session.flush()
    _db.session.add(PatientAccount(user_id=u.id, patient_id=portal_patient.id, tenant_id=test_tenant.id))
    _db.session.commit()
    return u


@pytest.fixture(scope='function')
def unlinked_portal_user(app, test_tenant):
    suffix = uuid.uuid4().hex[:6]
    u = User(
        username=f'unlinked_{suffix}',
        email=f'unlinked_{suffix}@test.local',
        full_name='مريض غير مربوط',
        role='patient',
        is_active=True,
        tenant_id=test_tenant.id,
    )
    u.set_password('test123')
    _db.session.add(u)
    _db.session.commit()
    return u


@pytest.fixture(scope='function')
def portal_auth_client(app, client, portal_user, test_tenant):
    from app.core.rate_limiter import _shared_store
    _shared_store.clear()
    client.post('/auth/login', data={
        'username': portal_user.username,
        'password': 'test123',
        'tenant_slug': test_tenant.slug,
    })
    return client


@pytest.fixture(scope='function')
def unlinked_auth_client(app, client, unlinked_portal_user, test_tenant):
    from app.core.rate_limiter import _shared_store
    _shared_store.clear()
    client.post('/auth/login', data={
        'username': unlinked_portal_user.username,
        'password': 'test123',
        'tenant_slug': test_tenant.slug,
    })
    return client


class TestPublicLanding:
    def test_landing_page_public(self, client):
        resp = client.get('/')
        assert resp.status_code == 200
        assert 'حجز موعد'.encode('utf-8') in resp.data

    def test_public_booking_index(self, client):
        resp = client.get('/booking/')
        assert resp.status_code == 200


class TestPatientPortalIdentity:
    def test_unlinked_user_sees_link_form(self, unlinked_auth_client):
        resp = unlinked_auth_client.get('/portal/link-account')
        assert resp.status_code == 200
        assert 'التحقق من هوية'.encode('utf-8') in resp.data

    def test_link_account_by_national_id(self, unlinked_auth_client, portal_patient, unlinked_portal_user):
        resp = unlinked_auth_client.post('/portal/link-account', data={
            'national_id': portal_patient.national_id,
            'phone': portal_patient.phone,
        }, follow_redirects=True)
        assert resp.status_code == 200
        link = PatientAccount.query.filter_by(user_id=unlinked_portal_user.id).first()
        assert link is not None
        assert link.patient_id == portal_patient.id

    def test_staff_cannot_access_portal_dashboard(self, manager_auth_client):
        resp = manager_auth_client.get('/portal/dashboard')
        assert resp.status_code in (302, 403)


class TestPatientPortalFeatures:
    def test_dashboard_loads_for_linked_patient(self, portal_auth_client, portal_patient):
        resp = portal_auth_client.get('/portal/dashboard')
        assert resp.status_code == 200

    def test_settings_save_preferences(self, portal_auth_client, portal_user):
        resp = portal_auth_client.post('/portal/settings', data={
            'notify_results': '1',
            'notify_appointments': '1',
            'marketing_contact': '0',
            'telemedicine_consent': '1',
        }, follow_redirects=True)
        assert resp.status_code == 200
        link = PatientAccount.query.filter_by(user_id=portal_user.id).first()
        prefs = link.portal_preferences or {}
        assert prefs.get('telemedicine_consent') is True
        assert prefs.get('marketing_contact') is False

    def test_documents_page_loads(self, portal_auth_client):
        resp = portal_auth_client.get('/portal/documents')
        assert resp.status_code == 200

    def test_book_appointment_redirects_to_public_booking(self, portal_auth_client):
        resp = portal_auth_client.get('/portal/book-appointment', follow_redirects=False)
        assert resp.status_code == 302
        assert '/booking' in (resp.location or '')
