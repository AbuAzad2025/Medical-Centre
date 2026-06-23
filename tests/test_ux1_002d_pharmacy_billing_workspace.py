"""Tests for UX1-002D: Pharmacy & Billing Workspace dashboards."""

import pytest

from app.extensions import db
from models.user import User


@pytest.fixture(scope='function')
def pharmacist_user(app, test_tenant):
    u = User.query.filter_by(username='pharmacist_test').first()
    if not u:
        u = User(
            username='pharmacist_test',
            email='pharmacist@test.local',
            full_name='صيدلي اختبار',
            role='pharmacist',
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
def accountant_user(app, test_tenant):
    u = User.query.filter_by(username='accountant_test_ux1').first()
    if not u:
        u = User(
            username='accountant_test_ux1',
            email='accountant_ux1@test.local',
            full_name='محاسب اختبار',
            role='accountant',
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
def pharmacy_auth_client(app, client, pharmacist_user, test_tenant):
    from app.core.rate_limiter import _shared_store
    _shared_store.clear()
    resp = client.post('/auth/login', data={
        'username': 'pharmacist_test',
        'password': 'test123',
        'tenant_slug': test_tenant.slug,
    }, follow_redirects=True)
    assert resp.status_code == 200
    return client


@pytest.fixture(scope='function')
def billing_auth_client(app, client, accountant_user, test_tenant):
    from app.core.rate_limiter import _shared_store
    _shared_store.clear()
    resp = client.post('/auth/login', data={
        'username': 'accountant_test_ux1',
        'password': 'test123',
        'tenant_slug': test_tenant.slug,
    }, follow_redirects=True)
    assert resp.status_code == 200
    return client


class TestPharmacyWorkspace:
    def test_dashboard_renders_with_stock_prescriptions_sales(self, pharmacy_auth_client):
        resp = pharmacy_auth_client.get('/medication/dashboard')
        text = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert 'لوحة تحكم الصيدلية' in text
        assert 'أدوية منخفضة المخزون' in text
        assert 'روشتات في الانتظار' in text
        assert 'مبيعات اليوم' in text


class TestBillingWorkspace:
    def test_dashboard_renders_with_invoices_and_payments(self, billing_auth_client):
        resp = billing_auth_client.get('/finance/dashboard')
        text = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert 'لوحة تحكم الفوترة' in text
        assert 'الفواتير الأخيرة' in text
