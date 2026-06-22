"""Tests for P0C-004: tenant-scoped route access and mutations.

Verifies that users cannot read or mutate resources that belong to other
tenants through lab catalog, lab panels, medication catalog, pharmacy POS,
suppliers, and purchase routes.
"""

import json
import uuid

import pytest

from app_factory import db as _db
from app.shared.enums import ProductProfile
from models.lab_test_catalog import LabTestCatalog, LabTestPanel
from models.medication import Medication, PharmacySale, Supplier, MedicationPurchase
from models.user import User
from app.core.tenant.models import Tenant


@pytest.fixture(scope='function')
def tenant_a(app):
    t = Tenant.query.filter_by(slug='tenant-a').first()
    if not t:
        t = Tenant(
            slug='tenant-a',
            name='Tenant A',
            contact_email='a@example.com',
            status='active',
            product_profile_code=ProductProfile.STANDALONE_PHARMACY,
        )
        _db.session.add(t)
        _db.session.commit()
    return t


@pytest.fixture(scope='function')
def tenant_b(app):
    t = Tenant.query.filter_by(slug='tenant-b').first()
    if not t:
        t = Tenant(
            slug='tenant-b',
            name='Tenant B',
            contact_email='b@example.com',
            status='active',
            product_profile_code=ProductProfile.STANDALONE_PHARMACY,
        )
        _db.session.add(t)
        _db.session.commit()
    return t


@pytest.fixture(scope='function')
def manager_a(app, tenant_a):
    u = User.query.filter_by(username='manager_a').first()
    if not u:
        u = User(
            username='manager_a',
            email='ma@example.com',
            full_name='Manager A',
            role='manager',
            is_active=True,
            tenant_id=tenant_a.id,
        )
        u.set_password('test123')
        _db.session.add(u)
        _db.session.commit()
    return u


@pytest.fixture(scope='function')
def client_a(app, client, manager_a, tenant_a):
    from app.core.rate_limiter import _shared_store
    _shared_store.clear()
    client.post('/auth/login', data={
        'username': 'manager_a',
        'password': 'test123',
        'tenant_slug': tenant_a.slug,
    })
    return client


@pytest.fixture(scope='function')
def medication_b(app, tenant_b):
    m = Medication(
        tenant_id=tenant_b.id,
        trade_name='TenantB Med',
        scientific_name='MedB',
        dosage_form='tablet',
        strength='500mg',
        price=10.0,
        stock_quantity=100,
        minimum_stock=10,
        is_active=True,
    )
    _db.session.add(m)
    _db.session.commit()
    return m


@pytest.fixture(scope='function')
def supplier_b(app, tenant_b):
    s = Supplier(
        tenant_id=tenant_b.id,
        name='TenantB Supplier',
        is_active=True,
    )
    _db.session.add(s)
    _db.session.commit()
    return s


@pytest.fixture(scope='function')
def purchase_b(app, tenant_b, medication_b, supplier_b):
    p = MedicationPurchase(
        tenant_id=tenant_b.id,
        medication_id=medication_b.id,
        supplier_id=supplier_b.id,
        batch_number='BATCH-B',
        quantity=10,
        remaining_quantity=10,
        purchase_price=5.0,
    )
    _db.session.add(p)
    _db.session.commit()
    return p


@pytest.fixture(scope='function')
def sale_b(app, tenant_b):
    s = PharmacySale(
        tenant_id=tenant_b.id,
        total_amount=100.0,
        status='completed',
    )
    _db.session.add(s)
    _db.session.commit()
    return s


@pytest.fixture(scope='function')
def lab_test_b(app, tenant_b):
    code = f'TB{uuid.uuid4().hex[:8].upper()}'
    t = LabTestCatalog(
        tenant_id=tenant_b.id,
        code=code,
        name_ar='فحص TenantB',
        name_en='TenantB Test',
        category='chemistry',
        is_active=True,
    )
    _db.session.add(t)
    _db.session.commit()
    return t


@pytest.fixture(scope='function')
def lab_panel_b(app, tenant_b):
    p = LabTestPanel(
        tenant_id=tenant_b.id,
        name_ar='باقة TenantB',
        name_en='TenantB Panel',
        is_active=True,
    )
    _db.session.add(p)
    _db.session.commit()
    return p


class TestMedicationCatalogIsolation:
    def test_medication_list_excludes_other_tenant(self, client_a, medication_b):
        resp = client_a.get('/medication/list')
        assert resp.status_code == 200
        assert b'TenantB Med' not in resp.data

    def test_medication_edit_requires_same_tenant(self, client_a, medication_b):
        resp = client_a.post(
            f'/medication/edit/{medication_b.id}',
            data={
                'trade_name': 'Hacked',
                'scientific_name': 'Hacked',
                'stock_quantity': 0,
                'minimum_stock': 0,
                'price': 0,
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        _db.session.refresh(medication_b)
        assert medication_b.trade_name == 'TenantB Med'


class TestSupplierIsolation:
    def test_supplier_list_excludes_other_tenant(self, client_a, supplier_b):
        resp = client_a.get('/medication/suppliers')
        assert resp.status_code == 200
        assert b'TenantB Supplier' not in resp.data

    def test_supplier_edit_requires_same_tenant(self, client_a, supplier_b):
        resp = client_a.post(
            f'/medication/suppliers/{supplier_b.id}/edit',
            data={'name': 'Hacked Supplier'},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        _db.session.refresh(supplier_b)
        assert supplier_b.name == 'TenantB Supplier'

    def test_supplier_delete_requires_same_tenant(self, client_a, supplier_b):
        resp = client_a.post(
            f'/medication/suppliers/{supplier_b.id}/delete',
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert Supplier.query.get(supplier_b.id) is not None

    def test_purchase_list_excludes_other_tenant(self, client_a, purchase_b):
        resp = client_a.get('/medication/purchases')
        assert resp.status_code == 200
        assert purchase_b.batch_number.encode() not in resp.data


class TestPosIsolation:
    def test_pos_interface_excludes_other_tenant_medication(self, client_a, medication_b):
        resp = client_a.get('/medication/pos')
        assert resp.status_code == 200
        assert b'TenantB Med' not in resp.data

    def test_pos_api_search_excludes_other_tenant(self, client_a, medication_b):
        resp = client_a.get('/medication/api/medications/search?q=TenantB')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert not any('TenantB' in str(item.get('trade_name', '')) for item in data)

    def test_pos_sell_rejects_other_tenant_medication(self, client_a, medication_b):
        resp = client_a.post(
            '/medication/pos/sell',
            json={
                'items': [{'medication_id': medication_b.id, 'quantity': 1}],
                'customer_name': 'Test',
            },
            content_type='application/json',
        )
        assert resp.status_code in (400, 403, 404)
        _db.session.refresh(medication_b)
        assert medication_b.stock_quantity == 100

    def test_sales_history_excludes_other_tenant(self, client_a, sale_b):
        resp = client_a.get('/medication/sales-history')
        assert resp.status_code == 200
        # Sale number is rendered as a zero-padded invoice number
        assert f'#{sale_b.id:06d}'.encode() not in resp.data


class TestLabCatalogIsolation:
    def test_lab_catalog_edit_requires_same_tenant(self, client_a, lab_test_b):
        original_code = lab_test_b.code
        resp = client_a.post(
            f'/lab/test-catalog/{lab_test_b.id}/edit',
            data={
                'code': 'HACKED',
                'name_ar': 'مخترق',
                'name_en': 'Hacked',
                'category': 'chemistry',
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        _db.session.refresh(lab_test_b)
        assert lab_test_b.code == original_code

    def test_lab_catalog_delete_requires_same_tenant(self, client_a, lab_test_b):
        resp = client_a.post(
            f'/lab/test-catalog/{lab_test_b.id}/delete',
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert LabTestCatalog.query.get(lab_test_b.id) is not None

    def test_lab_api_item_excludes_other_tenant(self, client_a, lab_test_b):
        resp = client_a.get(f'/lab/api/test-catalog/{lab_test_b.id}')
        assert resp.status_code == 404

    def test_lab_panel_edit_requires_same_tenant(self, client_a, lab_panel_b):
        resp = client_a.post(
            f'/lab/test-panels/{lab_panel_b.id}/edit',
            data={
                'name_ar': 'مخترق',
                'name_en': 'Hacked',
                'test_ids': [],
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        _db.session.refresh(lab_panel_b)
        assert lab_panel_b.name_ar == 'باقة TenantB'

    def test_lab_panel_delete_requires_same_tenant(self, client_a, lab_panel_b):
        resp = client_a.post(
            f'/lab/test-panels/{lab_panel_b.id}/delete',
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert LabTestPanel.query.get(lab_panel_b.id) is not None
