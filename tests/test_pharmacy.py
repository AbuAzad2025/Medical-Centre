"""
Pharmacy POS, catalog, suppliers, and purchase tests.
"""

from datetime import UTC

from flask import g
from sqlalchemy import select

from app.extensions import db
from models.medication import Medication, Prescription, PrescriptionItem
from models.patient import Patient
from models.user import User
from models.visit import Visit

# Trade name of the row owned by the *other* tenant in the isolation test.
# One constant for both the write and the read: if they ever drift the read
# matches nothing and the isolation assertion holds vacuously.
OTHER_TRADE_NAME = 'دواء منشأة أخرى'


class TestMedicationCatalog:
    """Medication CRUD and search tests."""

    def test_list_medications(self, auth_client, test_medications):
        resp = auth_client.get('/medication/list')
        assert resp.status_code == 200
        assert 'أموكسيسيلين' in resp.data.decode('utf-8')

    def test_add_medication(self, auth_client, test_tenant):
        import secrets

        unique_name = 'دواء تجريبي ' + secrets.token_hex(4)
        resp = auth_client.post(
            '/medication/add',
            data={
                'trade_name': unique_name,
                'scientific_name': 'Test Drug',
                'dosage_form': 'capsule',
                'strength': '250mg',
                'price': 12.00,
                'stock_quantity': 50,
                'minimum_stock': 10,
                'category': 'antibiotic',
            },
        )
        assert resp.status_code == 302

        m = (
            db.session.execute(select(Medication).filter_by(trade_name=unique_name))
            .scalars()
            .first()
        )
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
        resp = auth_client.post(
            '/medication/pos/sell',
            json={
                'items': [{'medication_id': med.id, 'quantity': 2, 'unit_price': float(med.price)}],
                'customer_name': 'عميل تجريبي',
                'payment_method': 'cash',
            },
            content_type='application/json',
        )

        from models.medication import PharmacySale

        sale = (
            db.session.execute(select(PharmacySale).filter_by(customer_name='عميل تجريبي'))
            .scalars()
            .first()
        )
        if sale is None and resp.status_code == 200:
            data = resp.get_json()
            assert data is not None
            assert data.get('success') or data.get('sale_id')
            sale = db.session.get(PharmacySale, data.get('sale_id'))

        assert sale is not None, 'Sale was not created'
        assert float(sale.total_amount) > 0
        med_updated = db.session.get(Medication, med.id)
        assert med_updated.stock_quantity == original_stock - 2

    def test_pos_sell_without_customer(self, auth_client, test_tenant, test_medications):
        """POS sale must work WITHOUT customer name (standalone retail)."""
        med = test_medications[1]
        resp = auth_client.post(
            '/medication/pos/sell',
            json={
                'items': [{'medication_id': med.id, 'quantity': 1, 'unit_price': float(med.price)}],
                'payment_method': 'cash',
            },
            content_type='application/json',
        )
        assert resp.status_code in (200, 302)
        from models.medication import PharmacySale

        sale = db.session.execute(select(PharmacySale).order_by(PharmacySale.id.desc())).scalar()
        assert sale is not None
        assert sale.customer_name is None or sale.customer_name == ''

    def test_sales_history(self, auth_client, test_medications):
        from datetime import datetime

        from app_factory import db
        from models.medication import PharmacySale

        sale = PharmacySale(
            tenant_id=test_medications[0].tenant_id,
            total_amount=25.00,
            status='completed',
            customer_name='عميل تاريخ',
            created_at=datetime.now(UTC),
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
        resp = auth_client.get(f'/medication/sales/{sale.id}')
        assert resp.status_code in (200, 302)


class TestSuppliers:
    """Supplier CRUD tests."""

    def test_suppliers_page(self, auth_client):
        resp = auth_client.get('/medication/suppliers')
        assert resp.status_code == 200

    def test_add_supplier(self, auth_client, test_tenant):
        resp = auth_client.post(
            '/medication/suppliers/add',
            data={
                'name': 'مورد تجريبي',
                'contact_person': 'شخص اتصال',
                'phone': '0599000000',
                'email': 'supplier@test.local',
                'address': 'عنوان تجريبي',
            },
        )
        assert resp.status_code == 302
        from models.medication import Supplier

        s = db.session.execute(select(Supplier).filter_by(name='مورد تجريبي')).scalars().first()
        assert s is not None
        assert s.tenant_id == test_tenant.id

    def test_edit_supplier(self, auth_client, test_tenant):
        from app_factory import db
        from models.medication import Supplier

        s = Supplier(name='مورد قابل للتعديل', tenant_id=test_tenant.id)
        db.session.add(s)
        db.session.commit()
        resp = auth_client.post(
            f'/medication/suppliers/{s.id}/edit',
            data={
                'name': 'مورد معدل',
                'contact_person': 'شخص معدل',
                'phone': '0599111111',
            },
        )
        assert resp.status_code == 302
        updated = db.session.get(Supplier, s.id)
        assert updated.name == 'مورد معدل'

    def test_delete_supplier_forbidden(self, auth_client, test_tenant):
        """Pharmacist cannot delete suppliers (admin/manager only)."""
        from app_factory import db
        from models.medication import Supplier

        s = Supplier(name='مورد للحذف', tenant_id=test_tenant.id)
        db.session.add(s)
        db.session.commit()
        resp = auth_client.post(f'/medication/suppliers/{s.id}/delete')
        assert resp.status_code == 403
        deleted = db.session.get(Supplier, s.id)
        assert deleted is not None


class TestPurchases:
    """Medication purchase (batch/lot) recording tests."""

    def test_purchases_page(self, auth_client):
        resp = auth_client.get('/medication/purchases')
        assert resp.status_code == 200

    def test_add_purchase(self, auth_client, test_tenant, test_medications):
        import secrets

        from app_factory import db
        from models.medication import MedicationPurchase, Supplier

        s = Supplier(name='مورد مشتريات', tenant_id=test_tenant.id)
        db.session.add(s)
        db.session.commit()
        med = test_medications[0]
        original_stock = med.stock_quantity
        batch_number = 'BATCH-' + secrets.token_hex(6).upper()
        resp = auth_client.post(
            '/medication/purchases/add',
            data={
                'supplier_id': s.id,
                'medication_id': med.id,
                'quantity': 100,
                'purchase_price': 10.00,
                'batch_number': batch_number,
                'expiry_date': '2027-12-31',
            },
        )
        assert resp.status_code == 302
        purchase = (
            db.session.execute(select(MedicationPurchase).filter_by(batch_number=batch_number))
            .scalars()
            .first()
        )
        assert purchase is not None
        assert purchase.tenant_id == test_tenant.id
        assert float(purchase.purchase_price * purchase.quantity) == 1000.00
        med_updated = db.session.get(Medication, med.id)
        assert med_updated.stock_quantity == original_stock + 100


class TestTenantIsolation:
    """Tenant data isolation tests."""

    def test_tenant_filter_on_medications(self, app, test_tenant, test_medications):
        """Medications should be scoped to tenant."""

        g.tenant_id = test_tenant.id
        from models.medication import Medication

        meds = db.session.execute(select(Medication)).scalars().all()
        for m in meds:
            assert m.tenant_id == test_tenant.id
        g.tenant_id = None

    def test_cross_tenant_isolation(self, app, test_tenant):
        """Data from different tenant should not be visible."""

        from app.core.tenant.models import Tenant
        from app_factory import db
        from models.medication import Medication
        from tests.tenant_context import tenant_test_context

        other = db.session.execute(select(Tenant).filter_by(slug='other-test')).scalars().first()
        if not other:
            other = Tenant(
                slug='other-test',
                name='Other Test',
                status='active',
                contact_email='other@test.com',
            )
            db.session.add(other)
            db.session.commit()

        try:
            # `medications` carries a WITH CHECK policy. g._tenant_filter_bypass
            # is an ORM-side flag that never reaches PostgreSQL, so writing
            # tenant B's row from tenant A's context is rejected with
            # InsufficientPrivilege. Bind tenant B instead of weakening the
            # policy.
            with tenant_test_context(app, other):
                m = db.session.execute(
                    select(Medication).filter_by(tenant_id=other.id, trade_name=OTHER_TRADE_NAME)
                ).scalar()
                if not m:
                    m = Medication(
                        tenant_id=other.id,
                        trade_name=OTHER_TRADE_NAME,
                        scientific_name='Other Drug',
                        dosage_form='tablet',
                        strength='500mg',
                        price=10.00,
                        stock_quantity=10,
                        minimum_stock=5,
                    )
                    db.session.add(m)
                    db.session.commit()
                assert m.id is not None

            # Read back as tenant A, bound properly. Assigning `g.tenant_id` by
            # hand is not enough: `tenant_filter._current_tenant_id()` reads
            # `db.session.info['_tenant_id']` *before* `g.tenant_id`, and the
            # scope above left tenant B in that dict, so a manual assignment was
            # ignored and the query returned tenant B's own row.
            with tenant_test_context(app, test_tenant):
                meds = (
                    db.session.execute(
                        select(Medication).filter(Medication.trade_name == OTHER_TRADE_NAME)
                    )
                    .scalars()
                    .all()
                )
                assert len(meds) == 0

            # Tenant B still sees it, so the row was not simply never written and
            # the assertion above is measuring isolation rather than absence.
            with tenant_test_context(app, other):
                seen_by_owner = (
                    db.session.execute(
                        select(Medication).filter(Medication.trade_name == OTHER_TRADE_NAME)
                    )
                    .scalars()
                    .all()
                )
                assert len(seen_by_owner) == 1
        finally:
            # The shared app context outlives this test, so `g.tenant_id` left
            # naming tenant B silently re-scoped every later test in the run.
            db.session.info.pop('_tenant_id', None)
            g.pop('tenant_id', None)


class TestControlledDispenseAck:
    """G-1: controlled-substance dispense requires explicit acknowledgement."""

    def test_dispense_without_ack_rejected(self, auth_client, test_tenant, test_medications):
        from sqlalchemy import select

        g.tenant_id = test_tenant.id
        try:
            med = test_medications[0]
            med.is_controlled = True
            med.schedule = 'II'
            db.session.commit()

            p = (
                db.session.execute(select(Patient).filter_by(tenant_id=test_tenant.id))
                .scalars()
                .first()
            )
            if not p:
                p = Patient(first_name='Test', last_name='Patient', tenant_id=test_tenant.id)
                db.session.add(p)
                db.session.commit()

            doc = (
                db.session.execute(select(User).filter_by(role='doctor', tenant_id=test_tenant.id))
                .scalars()
                .first()
            )
            if not doc:
                doc = User(
                    username='doc_disp',
                    email='doc@x.com',
                    full_name='Doc',
                    role='doctor',
                    is_active=True,
                    tenant_id=test_tenant.id,
                )
                doc.set_password('p')
                db.session.add(doc)
                db.session.commit()

            v = Visit(
                patient_id=p.id, doctor_id=doc.id, tenant_id=test_tenant.id, payment_status='PAID'
            )
            db.session.add(v)
            db.session.commit()

            pres = Prescription(
                tenant_id=test_tenant.id,
                patient_id=p.id,
                doctor_id=doc.id,
                visit_id=v.id,
                prescription_number='RX-TEST1',
            )
            db.session.add(pres)
            db.session.flush()

            item = PrescriptionItem(
                prescription_id=pres.id,
                medication_id=med.id,
                dosage='1x1',
                quantity=2,
                duration_days=3,
                unit_price=med.price,
                total_price=med.price * 2,
            )
            db.session.add(item)
            db.session.commit()

            resp = auth_client.post(
                f'/medication/prescriptions/dispense/{pres.id}',
                json={'acknowledge_controlled': False},
                content_type='application/json',
            )
            assert resp.status_code == 428
            data = resp.get_json()
            assert data['code'] == 'CONTROLLED_REQUIRES_ACK'
            assert med.trade_name in data['message']

            resp = auth_client.post(
                f'/medication/prescriptions/dispense/{pres.id}',
                json={'acknowledge_controlled': True},
                content_type='application/json',
            )
            assert resp.status_code == 200
            pres = db.session.get(Prescription, pres.id)
            assert pres.status == 'dispensed'
        finally:
            g.tenant_id = None
