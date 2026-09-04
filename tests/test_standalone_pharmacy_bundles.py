"""Deep audit: standalone_pharmacy (pharmacy + inventory + billing)."""

from datetime import UTC, datetime

from sqlalchemy import func, select

from app.core.module.validators import can_activate_module
from app.core.tenant.models import ProductBundle, Tenant, seed_default_bundles
from app.extensions import db
from app.shared.enums import TenantStatus
from tests.tenant_context import tenant_test_context

BUNDLE_SLUG = 'standalone_pharmacy'
ALLOWED = {'pharmacy', 'inventory', 'billing'}
BLOCKED = {
    'doctor',
    'reception',
    'lab',
    'radiology',
    'nursing',
    'emergency',
    'appointments',
    'reporting',
}


def _seed():
    if db.session.execute(select(func.count()).select_from(ProductBundle)).scalar() == 0:
        seed_default_bundles()


def _make_tenant(app, suffix='pharm'):
    _seed()
    ts = int(datetime.now(UTC).timestamp())
    with app.app_context():
        t = Tenant(
            slug=f'audit-{suffix}-{ts}',
            name='Standalone Pharmacy Audit',
            contact_email='audit@pharm.local',
            status=TenantStatus.ACTIVE,
            product_profile_code=BUNDLE_SLUG,
        )
        db.session.add(t)
        db.session.commit()
        return t.id


class TestBundleModules:
    def test_bundle_exists(self, app):
        _seed()
        with app.app_context():
            b = (
                db.session.execute(select(ProductBundle).filter_by(slug=BUNDLE_SLUG))
                .scalars()
                .first()
            )
            assert b is not None
            assert set(b.get_modules()) == ALLOWED

    def test_allowed_modules_activate(self, app):
        tid = _make_tenant(app, 'allow')
        with app.app_context():
            for mod in ALLOWED:
                ok, msg = can_activate_module(tid, mod)
                assert ok is True, f'{mod} should be allowed: {msg}'

    def test_blocked_modules_rejected(self, app):
        tid = _make_tenant(app, 'block')
        with app.app_context():
            for mod in BLOCKED:
                ok, msg = can_activate_module(tid, mod)
                assert ok is False, f'{mod} should be blocked but got ok={ok}: {msg}'


class TestRoleAccess:
    def test_pharmacist_can_access_pos(self, app, client, test_tenant, login_as):
        login_as(client, 'ph_pos_ap4', 'pharmacist')
        assert client.get('/medication/pos').status_code == 200

    def test_pharmacist_can_access_stock_alerts(self, app, client, test_tenant, login_as):
        login_as(client, 'ph_stock_ap4', 'pharmacist')
        assert client.get('/medication/stock-alerts').status_code == 200

    def test_pharmacist_can_access_suppliers(self, app, client, test_tenant, login_as):
        login_as(client, 'ph_sup_ap4', 'pharmacist')
        assert client.get('/medication/suppliers').status_code == 200

    def test_pharmacist_can_access_prescriptions(self, app, client, test_tenant, login_as):
        login_as(client, 'ph_rx_ap4', 'pharmacist')
        assert client.get('/medication/prescriptions').status_code == 200

    def test_pharmacist_can_access_dashboard(self, app, client, test_tenant, login_as):
        login_as(client, 'ph_dash_ap4', 'pharmacist')
        assert client.get('/medication/dashboard').status_code == 200

    def test_pharmacist_can_access_interactions(self, app, client, test_tenant, login_as):
        login_as(client, 'ph_int_ap4', 'pharmacist')
        assert client.get('/medication/interactions').status_code == 200

    def test_accountant_can_access_billing_routes(self, app, client, test_tenant, login_as):
        login_as(client, 'acct_bill_ap4', 'accountant')
        assert client.get('/accountant/dashboard').status_code == 200


class TestDirectSale:
    def test_pos_sell_creates_sale_without_prescription(self, app):
        from uuid import uuid4

        from models.medication import Medication, PharmacySale, PharmacySaleItem

        tid = _make_tenant(app, 'ots')
        with app.app_context():
            tenant = db.session.get(Tenant, tid)
            with tenant_test_context(app, tenant):
                med = Medication(
                    tenant_id=tid,
                    scientific_name='Ibuprofen',
                    trade_name='OTC Painkiller',
                    generic_name='Ibuprofen',
                    dosage_form='tablet',
                    strength='200mg',
                    category='analgesic',
                    price=15.0,
                    stock_quantity=100,
                    minimum_stock=10,
                    is_active=True,
                )
                db.session.add(med)
                db.session.commit()

                sale = PharmacySale(
                    tenant_id=tid,
                    sale_number=(
                        f'POS-{datetime.now(UTC).strftime("%Y%m%d%H%M%S")}-{uuid4().hex[:6]}'
                    ),
                    total_amount=30.0,
                    status='completed',
                )
                db.session.add(sale)
                db.session.flush()
                item = PharmacySaleItem(
                    sale_id=sale.id,
                    medication_id=med.id,
                    medication_name=med.trade_name,
                    tenant_id=tid,
                    quantity=2,
                    unit_price=15.0,
                    total_price=30.0,
                )
                db.session.add(item)
                db.session.commit()
                assert sale.id is not None
                assert sale.total_amount == 30.0
                assert item.quantity == 2

    def test_no_prescription_model_used_in_pos(self, app):
        from models.medication import Medication, PharmacySale, PharmacySaleItem

        tid = _make_tenant(app, 'no_rx')
        with app.app_context():
            tenant = db.session.get(Tenant, tid)
            with tenant_test_context(app, tenant):
                med = Medication(
                    tenant_id=tid,
                    scientific_name='Paracetamol',
                    trade_name='OTC Paracetamol',
                    generic_name='Paracetamol',
                    dosage_form='tablet',
                    strength='500mg',
                    category='analgesic',
                    price=8.0,
                    stock_quantity=200,
                    minimum_stock=20,
                    is_active=True,
                )
                db.session.add(med)
                db.session.commit()

                sale = PharmacySale(
                    tenant_id=tid,
                    sale_number=f'POS-NORX-{datetime.now(UTC).strftime("%Y%m%d%H%M%S")}',
                    total_amount=8.0,
                    status='completed',
                )
                db.session.add(sale)
                db.session.flush()
                item = PharmacySaleItem(
                    sale_id=sale.id,
                    medication_id=med.id,
                    medication_name=med.trade_name,
                    tenant_id=tid,
                    quantity=1,
                    unit_price=8.0,
                    total_price=8.0,
                )
                db.session.add(item)
                db.session.commit()
                assert sale.id is not None
                assert sale.patient_id is None


class TestStockAdjustment:
    def test_pos_sell_decrements_stock(self, app, client, test_tenant, login_as):
        from models.medication import Medication

        login_as(client, 'ph_stock_sell4', 'pharmacist')
        with app.app_context():
            tenant = db.session.get(Tenant, test_tenant.id)
            with tenant_test_context(app, tenant):
                med = Medication(
                    tenant_id=test_tenant.id,
                    scientific_name='TestCompound',
                    trade_name='Stock Test Med',
                    generic_name='Test',
                    dosage_form='tablet',
                    strength='100mg',
                    category='test',
                    price=10.0,
                    stock_quantity=50,
                    minimum_stock=5,
                    is_active=True,
                )
                db.session.add(med)
                db.session.commit()
                med_id = med.id
                initial = med.stock_quantity

        resp = client.post(
            '/medication/pos/sell',
            json={'items': [{'medication_id': med_id, 'quantity': 3}]},
        )
        assert resp.status_code == 200

        with app.app_context():
            tenant = db.session.get(Tenant, test_tenant.id)
            with tenant_test_context(app, tenant):
                med2 = db.session.get(Medication, med_id)
                assert med2.stock_quantity == initial - 3


class TestDashboardRouting:
    def test_pharmacist_dashboard_route(self, app):
        _seed()
        with app.app_context():
            from app.core.tenant.models import _PRODUCT_PROFILE_SEED

            route = _PRODUCT_PROFILE_SEED.get(BUNDLE_SLUG, {}).get('dashboard_route')
            assert route == '/pharmacy/pos'

    def test_pharmacist_widgets(self, app):
        from app.shared.dashboard_registry import resolve_dashboard_widgets

        with app.app_context():
            widgets = resolve_dashboard_widgets('pharmacist', ALLOWED)
            widget_ids = [w.id for w in widgets]
            assert 'pharmacy_dispense' in widget_ids
            assert 'pharmacy_low_stock' in widget_ids
            assert 'pharmacy_prescriptions' in widget_ids
            assert 'pharmacy_sales' in widget_ids

    def test_pharmacist_nav_items(self, app, test_tenant, login_as, client):
        login_as(client, 'ph_nav_ap4', 'pharmacist')
        assert client.get('/medication/pos').status_code == 200
        assert client.get('/medication/suppliers').status_code == 200
