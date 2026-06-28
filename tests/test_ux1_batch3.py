"""Tests for Batch 3 — UX1 design system, inbox service, entitlements."""

import uuid

import pytest

from app.extensions import db
from models.user import User
from services.work_inbox_service import WorkInboxService
from services.patient_timeline_service import PatientTimelineService


@pytest.fixture(scope='function')
def reception_inbox_user(app, test_tenant):
    u = User.query.filter_by(username='batch3_inbox_user').first()
    if not u:
        u = User(
            username='batch3_inbox_user',
            email='batch3_inbox@test.local',
            full_name='موظف Batch3',
            role='reception',
            is_active=True,
            tenant_id=test_tenant.id,
        )
        u.set_password('test123')
        db.session.add(u)
        db.session.commit()
    yield u


@pytest.fixture(scope='function')
def batch3_accountant(app, test_tenant):
    u = User.query.filter_by(username='batch3_accountant').first()
    if not u:
        u = User(
            username='batch3_accountant',
            email='batch3_acc@test.local',
            full_name='محاسب Batch3',
            role='accountant',
            is_active=True,
            tenant_id=test_tenant.id,
        )
        u.set_password('test123')
        db.session.add(u)
        db.session.commit()
    yield u


@pytest.fixture(scope='function')
def batch3_billing_client(app, client, batch3_accountant, test_tenant):
    from app.core.rate_limiter import _shared_store
    _shared_store.clear()
    client.post('/auth/login', data={
        'username': 'batch3_accountant',
        'password': 'test123',
        'tenant_slug': test_tenant.slug,
    }, follow_redirects=True)
    return client


@pytest.fixture(scope='function')
def batch3_inbox_client(app, client, reception_inbox_user, test_tenant):
    from app.core.rate_limiter import _shared_store
    _shared_store.clear()
    client.post('/auth/login', data={
        'username': 'batch3_inbox_user',
        'password': 'test123',
        'tenant_slug': test_tenant.slug,
    }, follow_redirects=True)
    return client


class TestWorkInboxService:
    def test_get_inbox_items_returns_list(self, reception_inbox_user):
        items = WorkInboxService.get_inbox_items(reception_inbox_user)
        assert isinstance(items, list)

    def test_entitlement_locks_lab_without_capability(self, reception_inbox_user):
        items = WorkInboxService.get_inbox_items(
            reception_inbox_user,
            is_entitled=lambda k: k != 'lab_order',
        )
        lab_items = [i for i in items if i.get('item_type') == 'lab']
        for item in lab_items:
            assert item.get('entitled') is False


class TestPatientTimelineService:
    def test_summarize_empty(self):
        assert PatientTimelineService.summarize([]) == {}

    def test_build_events_empty_patient(self, app, test_tenant, monkeypatch):
        from models.patient import Patient
        monkeypatch.setattr(
            'app.shared.tenant_filter._check_bundle_limits_on_create',
            lambda instance, tenant_id: None,
        )
        p = Patient(
            first_name='Empty', last_name='Timeline',
            tenant_id=test_tenant.id,
        )
        db.session.add(p)
        db.session.commit()
        events = PatientTimelineService.build_events(p.id)
        assert isinstance(events, list)


class TestBillingDashboardBatch3:
    def test_finance_dashboard_shows_refund_policy(self, batch3_billing_client):
        resp = batch3_billing_client.get('/finance/dashboard')
        text = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert 'سياسة الاسترجاع' in text
        assert 'الفواتير الأخيرة' in text


class TestInboxUIBatch3:
    def test_inbox_renders_vsm_hint(self, batch3_inbox_client):
        resp = batch3_inbox_client.get('/inbox')
        text = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert 'صندوق العمل الموحد' in text
        assert 'VSM' in text or 'سير العمل' in text
