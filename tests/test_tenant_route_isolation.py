"""Tests for P0C-004: tenant-scoped route access and mutations.

Verifies that users cannot read or mutate resources that belong to other
tenants through lab catalog, lab panels, medication catalog, pharmacy POS,
suppliers, and purchase routes.
"""

import json
import uuid

import pytest
from sqlalchemy import select

from app.core.tenant.models import Tenant
from app.extensions import db
from app.shared.enums import ProductProfile
from app_factory import db as _db
from models.lab_test_catalog import LabTestCatalog, LabTestPanel
from models.medication import Medication, MedicationPurchase, PharmacySale, Supplier
from tests.tenant_context import (
    activate_tenant_modules,
    create_scoped,
    ensure_test_user,
    refresh_scoped,
    tenant_test_context,
)


@pytest.fixture(scope='function')
def tenant_a(app):
    from flask import g

    prev = g.get('_tenant_filter_bypass', False)
    g._tenant_filter_bypass = True
    try:
        t = db.session.execute(select(Tenant).filter_by(slug='tenant-a')).scalars().first()
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
        # Ensure pharmacy/medication modules are active (idempotent across test runs)
        # activate_tenant_modules binds the tenant, and does not swallow the
        # write. The loop it replaces caught every exception and rolled back, so
        # an RLS-rejected insert left the module inactive and the route under
        # test answered 403 from the module guard instead of failing here.
        activate_tenant_modules(app, t, ('pharmacy', 'medication', 'lab'))
    finally:
        if prev:
            g._tenant_filter_bypass = True
        else:
            g.pop('_tenant_filter_bypass', None)
    return t


@pytest.fixture(scope='function')
def tenant_b(app):
    from flask import g

    prev = g.get('_tenant_filter_bypass', False)
    g._tenant_filter_bypass = True
    try:
        t = db.session.execute(select(Tenant).filter_by(slug='tenant-b')).scalars().first()
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
        # activate_tenant_modules binds the tenant, and does not swallow the
        # write. The loop it replaces caught every exception and rolled back, so
        # an RLS-rejected insert left the module inactive and the route under
        # test answered 403 from the module guard instead of failing here.
        activate_tenant_modules(app, t, ('pharmacy', 'medication', 'lab'))
    finally:
        if prev:
            g._tenant_filter_bypass = True
        else:
            g.pop('_tenant_filter_bypass', None)
    return t


@pytest.fixture(scope='function')
def manager_a(app, tenant_a):
    """Create a unique manager user per test to avoid duplicate-key errors."""

    uid_suffix = uuid.uuid4().hex[:8]
    username = f'manager_a_{uid_suffix}'
    email = f'ma_{uid_suffix}@example.com'
    return ensure_test_user(
        db,
        tenant_a,
        username=username,
        role='manager',
        email=email,
        password='test123',
        full_name='Manager A',
    )


@pytest.fixture(scope='function')
def client_a(app, client, manager_a, tenant_a):
    from app.core.rate_limiter import _shared_store

    _shared_store.clear()
    client.post(
        '/auth/login',
        data={
            'username': manager_a.username,
            'password': 'test123',
            'tenant_slug': tenant_a.slug,
        },
    )
    with client.session_transaction() as sess:
        sess['_user_id'] = str(manager_a.id)
        sess['tenant_id'] = int(tenant_a.id)
        sess['tenant_slug'] = tenant_a.slug
        sess['_fresh'] = True
    # Two pieces of per-request state have to be dropped before the test makes
    # its own request. Under test the request reuses this app context, so:
    #
    #   * g._login_user — set by login_user() inside /auth/login — would make the
    #     request authenticate with the login view's stale instance (expired,
    #     attached to no session) instead of reading the session cookie, and every
    #     attribute read raised ObjectDeletedError on a user that exists;
    #   * g.tenant_id — bind_tenant_from_session() returns early when it is
    #     already set, so a leftover id from a fixture left the request bound to
    #     the wrong tenant while the connection GUC said another: the module
    #     guard then saw no active modules and answered 403.
    #
    # In production both die with the app context.
    from flask import g

    from tests.tenant_context import clear_tenant_g

    clear_tenant_g()
    g.pop('_login_user', None)
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
    return create_scoped(app, tenant_b, m)


@pytest.fixture(scope='function')
def supplier_b(app, tenant_b):
    s = Supplier(
        tenant_id=tenant_b.id,
        name='TenantB Supplier',
        is_active=True,
    )
    return create_scoped(app, tenant_b, s)


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
    return create_scoped(app, tenant_b, p)


@pytest.fixture(scope='function')
def sale_b(app, tenant_b):
    s = PharmacySale(
        tenant_id=tenant_b.id,
        total_amount=100.0,
        status='completed',
    )
    return create_scoped(app, tenant_b, s)


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
    return create_scoped(app, tenant_b, t)


@pytest.fixture(scope='function')
def lab_panel_b(app, tenant_b):
    p = LabTestPanel(
        tenant_id=tenant_b.id,
        name_ar='باقة TenantB',
        name_en='TenantB Panel',
        is_active=True,
    )
    return create_scoped(app, tenant_b, p)


@pytest.mark.no_tenant_context
class TestMedicationCatalogIsolation:
    def test_medication_list_excludes_other_tenant(self, client_a, medication_b):
        resp = client_a.get('/medication/list')
        assert resp.status_code == 200
        assert b'TenantB Med' not in resp.data

    def test_medication_edit_requires_same_tenant(self, app, client_a, medication_b, tenant_b):
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
        # Re-read tenant B's row inside tenant B. After the request the bound
        # tenant is A, so a bare refresh is evaluated against A, returns no row,
        # and reports a row that is present as missing.
        refresh_scoped(app, tenant_b, medication_b)
        assert medication_b.trade_name == 'TenantB Med'


@pytest.mark.no_tenant_context
class TestSupplierIsolation:
    def test_supplier_list_excludes_other_tenant(self, client_a, supplier_b):
        resp = client_a.get('/medication/suppliers')
        assert resp.status_code == 200
        assert b'TenantB Supplier' not in resp.data

    def test_supplier_edit_requires_same_tenant(self, app, client_a, supplier_b, tenant_b):
        resp = client_a.post(
            f'/medication/suppliers/{supplier_b.id}/edit',
            data={'name': 'Hacked Supplier'},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        refresh_scoped(app, tenant_b, supplier_b)
        assert supplier_b.name == 'TenantB Supplier'

    def test_supplier_delete_requires_same_tenant(self, app, client_a, supplier_b, tenant_b):
        resp = client_a.post(
            f'/medication/suppliers/{supplier_b.id}/delete',
            follow_redirects=True,
        )
        assert resp.status_code == 200
        # Look for the row where it lives: a bare get after the request is
        # evaluated against tenant A and would report a present row as gone.
        with tenant_test_context(app, tenant_b):
            assert db.session.get(Supplier, supplier_b.id) is not None

    def test_purchase_list_excludes_other_tenant(self, app, client_a, purchase_b, tenant_b):
        # Capture the marker where the row is visible. After the request the
        # bound tenant is A, so touching purchase_b.batch_number there is a
        # refresh that matches no row and reports the row as deleted.
        with tenant_test_context(app, tenant_b):
            marker = purchase_b.batch_number.encode()
        resp = client_a.get('/medication/purchases')
        assert resp.status_code == 200
        assert marker not in resp.data


@pytest.mark.no_tenant_context
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

    def test_pos_sell_rejects_other_tenant_medication(self, app, client_a, medication_b, tenant_b):
        resp = client_a.post(
            '/medication/pos/sell',
            json={
                'items': [{'medication_id': medication_b.id, 'quantity': 1}],
                'customer_name': 'Test',
            },
            content_type='application/json',
        )
        assert resp.status_code in (400, 403, 404)
        refresh_scoped(app, tenant_b, medication_b)
        assert medication_b.stock_quantity == 100

    def test_sales_history_excludes_other_tenant(self, app, client_a, sale_b, tenant_b):
        # Same reason as the purchase test: read the id where the row lives.
        with tenant_test_context(app, tenant_b):
            marker = f'#{sale_b.id:06d}'.encode()
        resp = client_a.get('/medication/sales-history')
        assert resp.status_code == 200
        # Sale number is rendered as a zero-padded invoice number
        assert marker not in resp.data


@pytest.mark.no_tenant_context
class TestLabCatalogIsolation:
    def test_lab_catalog_edit_requires_same_tenant(self, app, client_a, lab_test_b, tenant_b):
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
        refresh_scoped(app, tenant_b, lab_test_b)
        assert lab_test_b.code == original_code

    def test_lab_catalog_delete_requires_same_tenant(self, app, client_a, lab_test_b, tenant_b):
        resp = client_a.post(
            f'/lab/test-catalog/{lab_test_b.id}/delete',
            follow_redirects=True,
        )
        assert resp.status_code == 200
        with tenant_test_context(app, tenant_b):
            assert db.session.get(LabTestCatalog, lab_test_b.id) is not None

    def test_lab_api_item_excludes_other_tenant(self, client_a, lab_test_b):
        resp = client_a.get(f'/lab/api/test-catalog/{lab_test_b.id}')
        assert resp.status_code == 404

    def test_lab_panel_edit_requires_same_tenant(self, app, client_a, lab_panel_b, tenant_b):
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
        refresh_scoped(app, tenant_b, lab_panel_b)
        assert lab_panel_b.name_ar == 'باقة TenantB'

    def test_lab_panel_delete_requires_same_tenant(self, app, client_a, lab_panel_b, tenant_b):
        resp = client_a.post(
            f'/lab/test-panels/{lab_panel_b.id}/delete',
            follow_redirects=True,
        )
        assert resp.status_code == 200
        with tenant_test_context(app, tenant_b):
            assert db.session.get(LabTestPanel, lab_panel_b.id) is not None
