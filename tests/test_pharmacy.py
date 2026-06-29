"""
Pharmacy POS, catalog, suppliers, and purchase tests.
"""
import pytest
from decimal import Decimal


class TestMedicationCatalog:
    """Medication CRUD and search tests."""

    def test_list_medications(self, auth_client, test_medications):
        resp = auth_client.get('/medication/list')
        assert resp.status_code == 200
        assert 'أموكسيسيلين' in resp.data.decode('utf-8')

    def test_add_medication(self, auth_client, test_tenant):
        import secrets
        unique_name = 'دواء تجريبي ' + secrets.token_hex(4)
        resp = auth_client.post('/medication/add', data={
            'trade_name': unique_name,
            'scientific_name': 'Test Drug',
            'dosage_form': 'capsule',
            'strength': '250mg',
            'price': 12.00,
            'stock_quantity': 50,
            'minimum_stock': 10,
            'category': 'antibiotic',
        })
        assert resp.status_code == 302
        from models.medication import Medication
        m = Medication.query.filter_by(trade_name=unique_name).first()
        assert m is not None
        assert m.tenant_id == test_tenant.id

    def test_search_medication(self, auth_client, test_medications):
        resp = auth_client.get('/medication/list?search=أموكسيسيلين')
        assert resp.status_code == 200
        assert 'أموكسيسيلين' in resp.data.decode('utf-8')


class TestPharmacyPOS:
    """Point-of-Sale workflow tests."""

    def test_pos_page_loads(self, auth_client):
        resp = auth_client.get('/medication/pos')
        assert resp.status_code == 200

    def test_api_medications_search(self, auth_client, test_medications):
        resp = auth_client.get('/medication/api/medications/search?q=أموكسيسيلين')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data is not None
        assert len(data) >= 1

    def test_pos_sell_with_customer(self, auth_client, test_tenant, test_medications):
        med = test_medications[0]
        original_stock = med.stock_quantity
        resp = auth_client.post('/medication/pos/sell', json={
            'items': [
                {'medication_id': med.id, 'quantity': 2, 'unit_price': float(med.price)}
            ],
            'customer_name': 'عميل تجريبي',
            'payment_method': 'cash',
        }, content_type='application/json')

        from models.medication import PharmacySale, Medication
        sale = PharmacySale.query.filter_by(customer_name='عميل تجريبي').first()
        if sale is None and resp.status_code == 200:
            data = resp.get_json()
            assert data is not None
            assert data.get('success') or data.get('sale_id')
            sale = PharmacySale.query.get(data.get('sale_id'))

        assert sale is not None, "Sale was not created"
        assert float(sale.total_amount) > 0
        med_updated = Medication.query.get(med.id)
        assert med_updated.stock_quantity == original_stock - 2

    def test_pos_sell_without_customer(self, auth_client, test_tenant, test_medications):
        """POS sale must work WITHOUT customer name (standalone retail)."""
        med = test_medications[1]
        resp = auth_client.post('/medication/pos/sell', json={
            'items': [
                {'medication_id': med.id, 'quantity': 1, 'unit_price': float(med.price)}
            ],
            'payment_method': 'cash',
        }, content_type='application/json')
        assert resp.status_code in (200, 302)
        from models.medication import PharmacySale
        sale = PharmacySale.query.order_by(PharmacySale.id.desc()).first()
        assert sale is not None
        assert sale.customer_name is None or sale.customer_name == ''

    def test_sales_history(self, auth_client, test_medications):
        from app_factory import db
        from models.medication import PharmacySale
        from datetime import datetime, timezone
        sale = PharmacySale(
            tenant_id=test_medications[0].tenant_id,
            total_amount=25.00,
            status='completed',
            customer_name='عميل تاريخ',
            created_at=datetime.now(timezone.utc),
        )
        db.session.add(sale)
        db.session.commit()
        resp = auth_client.get('/medication/sales-history')
        assert resp.status_code == 200

    def test_sale_receipt(self, auth_client, test_medications):
        from app_factory import db
        from models.medication import PharmacySale
        sale = PharmacySale(
            tenant_id=test_medications[0].tenant_id,
            total_amount=15.00,
            status='completed',
        )
        db.session.add(sale)
        db.session.commit()
        resp = auth_client.get('/medication/sales/%d' % sale.id)
        assert resp.status_code in (200, 302)


class TestSuppliers:
    """Supplier CRUD tests."""

    def test_suppliers_page(self, auth_client):
        resp = auth_client.get('/medication/suppliers')
        assert resp.status_code == 200

    def test_add_supplier(self, auth_client, test_tenant):
        resp = auth_client.post('/medication/suppliers/add', data={
            'name': 'مورد تجريبي',
            'contact_person': 'شخص اتصال',
            'phone': '0599000000',
            'email': 'supplier@test.local',
            'address': 'عنوان تجريبي',
        })
        assert resp.status_code == 302
        from models.medication import Supplier
        s = Supplier.query.filter_by(name='مورد تجريبي').first()
        assert s is not None
        assert s.tenant_id == test_tenant.id

    def test_edit_supplier(self, auth_client, test_tenant):
        from app_factory import db
        from models.medication import Supplier
        s = Supplier(name='مورد قابل للتعديل', tenant_id=test_tenant.id)
        db.session.add(s)
        db.session.commit()
        resp = auth_client.post('/medication/suppliers/%d/edit' % s.id, data={
            'name': 'مورد معدل',
            'contact_person': 'شخص معدل',
            'phone': '0599111111',
        })
        assert resp.status_code == 302
        updated = Supplier.query.get(s.id)
        assert updated.name == 'مورد معدل'

    def test_delete_supplier_forbidden(self, auth_client, test_tenant):
        """Pharmacist cannot delete suppliers (admin/manager only)."""
        from app_factory import db
        from models.medication import Supplier
        s = Supplier(name='مورد للحذف', tenant_id=test_tenant.id)
        db.session.add(s)
        db.session.commit()
        resp = auth_client.post('/medication/suppliers/%d/delete' % s.id)
        assert resp.status_code == 403
        deleted = Supplier.query.get(s.id)
        assert deleted is not None


class TestPurchases:
    """Medication purchase (batch/lot) recording tests."""

    def test_purchases_page(self, auth_client):
        resp = auth_client.get('/medication/purchases')
        assert resp.status_code == 200

    def test_add_purchase(self, auth_client, test_tenant, test_medications):
        import secrets
        from app_factory import db
        from models.medication import Supplier, MedicationPurchase, Medication
        s = Supplier(name='مورد مشتريات', tenant_id=test_tenant.id)
        db.session.add(s)
        db.session.commit()
        med = test_medications[0]
        original_stock = med.stock_quantity
        batch_number = 'BATCH-' + secrets.token_hex(6).upper()
        resp = auth_client.post('/medication/purchases/add', data={
            'supplier_id': s.id,
            'medication_id': med.id,
            'quantity': 100,
            'purchase_price': 10.00,
            'batch_number': batch_number,
            'expiry_date': '2027-12-31',
        })
        assert resp.status_code == 302
        purchase = MedicationPurchase.query.filter_by(batch_number=batch_number).first()
        assert purchase is not None
        assert purchase.tenant_id == test_tenant.id
        assert float(purchase.purchase_price * purchase.quantity) == 1000.00
        med_updated = Medication.query.get(med.id)
        assert med_updated.stock_quantity == original_stock + 100


class TestTenantIsolation:
    """Tenant data isolation tests."""

    def test_tenant_filter_on_medications(self, app, test_tenant, test_medications):
        """Medications should be scoped to tenant."""
        from flask import g
        g.tenant_id = test_tenant.id
        from models.medication import Medication
        meds = Medication.query.all()
        for m in meds:
            assert m.tenant_id == test_tenant.id
        g.tenant_id = None

    def test_cross_tenant_isolation(self, app, test_tenant):
        """Data from different tenant should not be visible."""
        from flask import g
        from app_factory import db
        from models.medication import Medication
        from app.core.tenant.models import Tenant

        g._tenant_filter_bypass = True
        try:
            other = Tenant.query.filter_by(slug='other-test').first()
            if not other:
                other = Tenant(slug='other-test', name='Other Test', status='active', contact_email='other@test.com')
                db.session.add(other)
                db.session.commit()
            other_tenant_id = other.id

            m = Medication.query.filter_by(
                tenant_id=other_tenant_id, trade_name='دواء منشأة أخرى'
            ).first()
            if not m:
                m = Medication(
                    tenant_id=other_tenant_id,
                    trade_name='دواء منشأة أخرى',
                    scientific_name='Other Drug',
                    dosage_form='tablet',
                    strength='500mg',
                    price=10.00,
                    stock_quantity=10,
                    minimum_stock=5,
                )
                db.session.add(m)
                db.session.commit()
        finally:
            g.pop('_tenant_filter_bypass', None)

        g.tenant_id = test_tenant.id
        meds = Medication.query.filter(Medication.trade_name == 'دواء منشأة أخرى').all()
        assert len(meds) == 0
        g.tenant_id = None
