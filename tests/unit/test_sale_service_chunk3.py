"""Unit tests for PharmacySaleService – create_sale, void_sale, get_prescription_status.

Chunk 3: commission/options, final-commit failure, and basic CRUD paths.
"""

from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.extensions import db
from app.shared.enums import PrescriptionState
from services.pharmacy_sale_service import PharmacySaleService
from tests.tenant_context import bind_tenant_on_g

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_prescription(app, test_tenant, patient_id, status='active'):
    """Insert a minimal Prescription row and return its id."""
    from app.extensions import db
    from models.medication import Prescription

    rx = Prescription(
        tenant_id=test_tenant.id,
        patient_id=patient_id,
        prescription_number=f'RX-TEST-{patient_id}',
        status=status,
    )
    db.session.add(rx)
    db.session.commit()
    return rx.id


def _make_patient(app, test_tenant):
    """Insert a minimal Patient row and return its id."""
    from app.extensions import db
    from models.patient import Patient

    p = Patient(
        tenant_id=test_tenant.id,
        first_name='Test',
        last_name='Patient',
        gender='M',
    )
    db.session.add(p)
    db.session.commit()
    return p.id


def _make_user(app, test_tenant, username='dispenser_test'):
    """Insert a minimal User row and return it."""
    from app.extensions import db
    from models.user import User

    u = (
        db.session.execute(select(User).filter_by(username=username, tenant_id=test_tenant.id))
        .scalars()
        .first()
    )
    if not u:
        u = User(
            tenant_id=test_tenant.id,
            username=username,
            email=f'{username}@test.local',
            full_name='Dispenser Test',
            role='pharmacist',
            is_active=True,
        )
        u.set_password('ValidPass123!')
        db.session.add(u)
        db.session.commit()
    return u


def _tenant_ctx(app, test_tenant):
    """Push a request context with tenant bound on g."""
    from app.extensions import db

    ctx = app.test_request_context()
    ctx.push()
    bind_tenant_on_g(test_tenant, db_session=db.session)
    return ctx


# ===========================================================================
# TestCreateSaleCommissionAndOptions
# ===========================================================================


class TestCreateSaleCommissionAndOptions:
    """Tests for PharmacySaleService.create_sale."""

    # -- success paths ------------------------------------------------------

    def test_create_sale_basic(self, app, test_tenant, test_medications):
        """Happy-path: single item sale commits and returns sale_id + total."""
        patient_id = _make_patient(app, test_tenant)
        rx_id = _make_prescription(app, test_tenant, patient_id)
        med = test_medications[0]

        items = [{'medication_id': med.id, 'quantity': 2, 'unit_price': 10.0}]
        result = PharmacySaleService.create_sale(
            prescription_id=rx_id,
            dispensed_by=_make_user(app, test_tenant).id,
            items=items,
            tenant_id=test_tenant.id,
        )

        assert 'sale_id' in result
        assert result['total_amount'] == 20.0

    def test_create_sale_multiple_items(self, app, test_tenant, test_medications):
        """Multi-item sale: total is the sum of qty * unit_price for each."""
        patient_id = _make_patient(app, test_tenant)
        rx_id = _make_prescription(app, test_tenant, patient_id)
        med1, med2 = test_medications[0], test_medications[1]

        items = [
            {'medication_id': med1.id, 'quantity': 2, 'unit_price': 10.0},
            {'medication_id': med2.id, 'quantity': 1, 'unit_price': 5.50},
        ]
        result = PharmacySaleService.create_sale(
            prescription_id=rx_id,
            dispensed_by=_make_user(app, test_tenant).id,
            items=items,
            tenant_id=test_tenant.id,
        )

        assert result['total_amount'] == pytest.approx(25.50)

    def test_create_sale_prescription_marked_dispensed(self, app, test_tenant, test_medications):
        """After a successful sale the prescription status should be DISPENSED."""
        from models.medication import Prescription

        patient_id = _make_patient(app, test_tenant)
        rx_id = _make_prescription(app, test_tenant, patient_id)
        med = test_medications[0]
        items = [{'medication_id': med.id, 'quantity': 1, 'unit_price': 8.0}]

        PharmacySaleService.create_sale(
            prescription_id=rx_id,
            dispensed_by=_make_user(app, test_tenant).id,
            items=items,
            tenant_id=test_tenant.id,
        )

        rx = db.session.get(Prescription, rx_id)
        assert rx.status == PrescriptionState.DISPENSED

    def test_create_sale_commission_fields(self, app, test_tenant, test_medications):
        """Sale row gets correct tenant_id and sale_number prefix."""
        from models.medication import PharmacySale

        patient_id = _make_patient(app, test_tenant)
        rx_id = _make_prescription(app, test_tenant, patient_id)
        med = test_medications[0]
        items = [{'medication_id': med.id, 'quantity': 1, 'unit_price': 4.0}]

        result = PharmacySaleService.create_sale(
            prescription_id=rx_id,
            dispensed_by=_make_user(app, test_tenant).id,
            items=items,
            tenant_id=test_tenant.id,
        )

        sale = db.session.get(PharmacySale, result['sale_id'])
        assert sale.tenant_id == test_tenant.id
        assert sale.sale_number.startswith('SALE-')

    # -- error paths --------------------------------------------------------

    def test_create_sale_prescription_not_found(self, app, test_tenant):
        """When prescription_id doesn't exist, return an error dict."""
        result = PharmacySaleService.create_sale(
            prescription_id=999_999,
            dispensed_by=_make_user(app, test_tenant).id,
            items=[],
            tenant_id=test_tenant.id,
        )
        assert 'error' in result

    def test_create_sale_final_commit_failure(self, app, test_tenant, test_medications):
        """When db.session.commit() raises, RuntimeError should propagate."""
        patient_id = _make_patient(app, test_tenant)
        rx_id = _make_prescription(app, test_tenant, patient_id)
        med = test_medications[0]
        items = [{'medication_id': med.id, 'quantity': 1, 'unit_price': 10.0}]

        with patch('services.pharmacy_sale_service.db') as mock_db:
            mock_db.session.commit.side_effect = Exception('db down')

            with pytest.raises(Exception):
                PharmacySaleService.create_sale(
                    prescription_id=rx_id,
                    dispensed_by=_make_user(app, test_tenant).id,
                    items=items,
                    tenant_id=test_tenant.id,
                )

    # -- option / edge-case paths -------------------------------------------

    def test_create_sale_empty_items(self, app, test_tenant):
        """Sale with zero items should still succeed with total 0."""
        patient_id = _make_patient(app, test_tenant)
        rx_id = _make_prescription(app, test_tenant, patient_id)

        result = PharmacySaleService.create_sale(
            prescription_id=rx_id,
            dispensed_by=_make_user(app, test_tenant).id,
            items=[],
            tenant_id=test_tenant.id,
        )

        assert result['total_amount'] == 0

    def test_create_sale_uses_g_tenant_when_none(self, app, test_tenant, test_medications):
        """When tenant_id is None the service should pick it up from g."""
        patient_id = _make_patient(app, test_tenant)
        rx_id = _make_prescription(app, test_tenant, patient_id)
        med = test_medications[0]
        items = [{'medication_id': med.id, 'quantity': 1, 'unit_price': 3.0}]

        ctx = _tenant_ctx(app, test_tenant)
        try:
            result = PharmacySaleService.create_sale(
                prescription_id=rx_id,
                dispensed_by=_make_user(app, test_tenant).id,
                items=items,
            )
        finally:
            ctx.pop()

        assert 'sale_id' in result


# ===========================================================================
# void_sale tests
# ===========================================================================


class TestVoidSale:
    """Tests for PharmacySaleService.void_sale."""

    def _create_sale(self, app, test_tenant):
        """Helper: create a real sale and return its id."""
        from app.extensions import db
        from models.medication import PharmacySale

        sale = PharmacySale(
            tenant_id=test_tenant.id,
            total_amount=50.0,
            status='completed',
        )
        db.session.add(sale)
        db.session.commit()
        return sale.id

    def test_void_sale_success(self, app, test_tenant):
        sale_id = self._create_sale(app, test_tenant)
        ctx = _tenant_ctx(app, test_tenant)
        try:
            result = PharmacySaleService.void_sale(sale_id, reason='test')
        finally:
            ctx.pop()
        assert result['status'] == PrescriptionState.CANCELLED

    def test_void_sale_not_found(self, app, test_tenant):
        ctx = _tenant_ctx(app, test_tenant)
        try:
            result = PharmacySaleService.void_sale(999_999)
        finally:
            ctx.pop()
        assert 'error' in result

    def test_void_sale_commit_failure(self, app, test_tenant):
        sale_id = self._create_sale(app, test_tenant)
        ctx = _tenant_ctx(app, test_tenant)
        try:
            with patch('services.pharmacy_sale_service.db') as mock_db:
                mock_db.session.commit.side_effect = Exception('db down')

                with pytest.raises(Exception):
                    PharmacySaleService.void_sale(sale_id)
        finally:
            ctx.pop()


# ===========================================================================
# get_prescription_status tests
# ===========================================================================


class TestGetPrescriptionStatus:
    """Tests for PharmacySaleService.get_prescription_status."""

    def test_prescription_status_success(self, app, test_tenant):
        patient_id = _make_patient(app, test_tenant)
        rx_id = _make_prescription(app, test_tenant, patient_id)

        ctx = _tenant_ctx(app, test_tenant)
        try:
            result = PharmacySaleService.get_prescription_status(
                prescription_id=rx_id,
            )
        finally:
            ctx.pop()
        assert result['prescription_id'] == rx_id
        assert result['status'] == 'active'

    def test_prescription_status_not_found(self, app, test_tenant):
        ctx = _tenant_ctx(app, test_tenant)
        try:
            result = PharmacySaleService.get_prescription_status(
                prescription_id=999_999,
            )
        finally:
            ctx.pop()
        assert 'error' in result


# ===========================================================================
# POS Prescription Lookup (read-only preview)
# ===========================================================================


class TestPOSPrescriptionLookup:
    """Tests for PharmacySaleService.fetch_prescription_for_pos_cart."""

    def test_lookup_returns_cart_payload(self, app, test_tenant, test_medications):
        """POS lookup returns cart items without modifying prescription status."""
        from models.medication import Prescription, PrescriptionItem

        patient_id = _make_patient(app, test_tenant)
        rx_number = f'RX-POS-LOOKUP-{patient_id}'
        rx = Prescription(
            tenant_id=test_tenant.id,
            patient_id=patient_id,
            prescription_number=rx_number,
            status='active',
        )
        db.session.add(rx)
        db.session.commit()

        med = test_medications[0]
        item = PrescriptionItem(
            tenant_id=test_tenant.id,
            prescription_id=rx.id,
            medication_id=med.id,
            dosage='1 tablet',
            quantity=3,
            duration_days=7,
            unit_price=15.0,
            total_price=45.0,
        )
        db.session.add(item)
        db.session.commit()

        ctx = _tenant_ctx(app, test_tenant)
        try:
            cart = PharmacySaleService.fetch_prescription_for_pos_cart(
                prescription_id=rx.id, tenant_id=test_tenant.id
            )
        finally:
            ctx.pop()

        assert 'error' not in cart
        assert cart['prescription_id'] == rx.id
        assert cart['prescription_number'] == rx_number
        assert len(cart['items']) == 1
        assert cart['items'][0]['medication_id'] == med.id
        assert cart['items'][0]['quantity'] == 3
        assert cart['total_amount'] == 45.0

        # Read-only: status must not have changed
        rx_after = db.session.get(Prescription, rx.id)
        assert rx_after.status == 'active'

    def test_lookup_prescription_not_found(self, app, test_tenant):
        """Unknown prescription_id returns error dict."""
        ctx = _tenant_ctx(app, test_tenant)
        try:
            cart = PharmacySaleService.fetch_prescription_for_pos_cart(
                prescription_id=999_999, tenant_id=test_tenant.id
            )
        finally:
            ctx.pop()
        assert 'error' in cart

    def test_lookup_inactive_prescription_rejected(self, app, test_tenant, test_medications):
        """Prescription with non-eligible status is rejected."""
        from models.medication import Prescription, PrescriptionItem

        patient_id = _make_patient(app, test_tenant)
        rx_number = f'RX-POS-DISABLED-{patient_id}'
        rx = Prescription(
            tenant_id=test_tenant.id,
            patient_id=patient_id,
            prescription_number=rx_number,
            status='cancelled',
        )
        db.session.add(rx)
        db.session.commit()

        med = test_medications[0]
        item = PrescriptionItem(
            tenant_id=test_tenant.id,
            prescription_id=rx.id,
            medication_id=med.id,
            dosage='1 tablet',
            quantity=1,
            duration_days=7,
            unit_price=10.0,
            total_price=10.0,
        )
        db.session.add(item)
        db.session.commit()

        ctx = _tenant_ctx(app, test_tenant)
        try:
            cart = PharmacySaleService.fetch_prescription_for_pos_cart(
                prescription_id=rx.id, tenant_id=test_tenant.id
            )
        finally:
            ctx.pop()
        assert 'error' in cart

    def test_lookup_tenant_isolation(self, app, test_tenant, test_medications):
        """POS lookup filters by tenant_id at query level."""
        from models.medication import Prescription, PrescriptionItem

        patient_id = _make_patient(app, test_tenant)
        rx_number = f'RX-ISOLATION-{patient_id}'
        rx = Prescription(
            tenant_id=test_tenant.id,
            patient_id=patient_id,
            prescription_number=rx_number,
            status='active',
        )
        db.session.add(rx)
        db.session.commit()

        med = test_medications[0]
        item = PrescriptionItem(
            tenant_id=test_tenant.id,
            prescription_id=rx.id,
            medication_id=med.id,
            dosage='1 tablet',
            quantity=1,
            duration_days=7,
            unit_price=10.0,
            total_price=10.0,
        )
        db.session.add(item)
        db.session.commit()

        # Querying with a mismatched tenant_id must not return the prescription
        ctx = _tenant_ctx(app, test_tenant)
        try:
            cart = PharmacySaleService.fetch_prescription_for_pos_cart(
                prescription_id=rx.id, tenant_id=999_999
            )
        finally:
            ctx.pop()
        assert 'error' in cart


# ===========================================================================
# POS Atomic Dispense (row-level locking + dispense log)
# ===========================================================================


class TestPOSAtomicDispense:
    """Tests for atomic POS dispense in PharmacySaleService.create_sale."""

    def test_create_sale_with_pos_prescription_sets_dispensed(self, app, test_tenant, test_medications):
        """After POS sale the prescription status becomes DISPENSED."""
        from models.medication import Prescription, PrescriptionItem

        patient_id = _make_patient(app, test_tenant)
        rx_number = f'RX-POS-ATOMIC-{patient_id}'
        rx = Prescription(
            tenant_id=test_tenant.id,
            patient_id=patient_id,
            prescription_number=rx_number,
            status='active',
        )
        db.session.add(rx)
        db.session.commit()

        med = test_medications[0]
        item = PrescriptionItem(
            tenant_id=test_tenant.id,
            prescription_id=rx.id,
            medication_id=med.id,
            dosage='1 tablet',
            quantity=2,
            duration_days=7,
            unit_price=10.0,
            total_price=20.0,
        )
        db.session.add(item)
        db.session.commit()

        ctx = _tenant_ctx(app, test_tenant)
        try:
            result = PharmacySaleService.create_sale(
                prescription_id=rx.id,
                dispensed_by=_make_user(app, test_tenant).id,
                items=[{'medication_id': med.id, 'quantity': 2, 'unit_price': 10.0}],
                tenant_id=test_tenant.id,
            )
        finally:
            ctx.pop()

        assert 'sale_id' in result
        rx_after = db.session.get(Prescription, rx.id)
        assert rx_after.status == PrescriptionState.DISPENSED

    def test_create_sale_pos_creates_dispense_log(self, app, test_tenant, test_medications):
        """POS sale creates a PrescriptionDispenseLog entry."""
        from models.medication import Prescription, PrescriptionItem, PrescriptionDispenseLog

        patient_id = _make_patient(app, test_tenant)
        rx_number = f'RX-POS-LOG-{patient_id}'
        rx = Prescription(
            tenant_id=test_tenant.id,
            patient_id=patient_id,
            prescription_number=rx_number,
            status='active',
        )
        db.session.add(rx)
        db.session.commit()

        med = test_medications[0]
        item = PrescriptionItem(
            tenant_id=test_tenant.id,
            prescription_id=rx.id,
            medication_id=med.id,
            dosage='1 tablet',
            quantity=1,
            duration_days=7,
            unit_price=10.0,
            total_price=10.0,
        )
        db.session.add(item)
        db.session.commit()

        ctx = _tenant_ctx(app, test_tenant)
        try:
            result = PharmacySaleService.create_sale(
                prescription_id=rx.id,
                dispensed_by=_make_user(app, test_tenant).id,
                items=[{'medication_id': med.id, 'quantity': 1, 'unit_price': 10.0}],
                tenant_id=test_tenant.id,
            )
        finally:
            ctx.pop()

        logs = (
            db.session.execute(
                select(PrescriptionDispenseLog).filter_by(prescription_id=rx.id)
            )
            .scalars()
            .all()
        )
        assert len(logs) >= 1
        assert logs[0].notes == 'Dispensed via POS sale'

    def test_create_sale_pos_already_dispensed_rejected(self, app, test_tenant, test_medications):
        """Dispensing an already-dispensed prescription returns an error."""
        from models.medication import Prescription, PrescriptionItem

        patient_id = _make_patient(app, test_tenant)
        rx_number = f'RX-POS-ALREADY-{patient_id}'
        rx = Prescription(
            tenant_id=test_tenant.id,
            patient_id=patient_id,
            prescription_number=rx_number,
            status='dispensed',
        )
        db.session.add(rx)
        db.session.commit()

        med = test_medications[0]
        item = PrescriptionItem(
            tenant_id=test_tenant.id,
            prescription_id=rx.id,
            medication_id=med.id,
            dosage='1 tablet',
            quantity=1,
            duration_days=7,
            unit_price=10.0,
            total_price=10.0,
        )
        db.session.add(item)
        db.session.commit()

        ctx = _tenant_ctx(app, test_tenant)
        try:
            result = PharmacySaleService.create_sale(
                prescription_id=rx.id,
                dispensed_by=_make_user(app, test_tenant).id,
                items=[{'medication_id': med.id, 'quantity': 1, 'unit_price': 10.0}],
                tenant_id=test_tenant.id,
            )
        finally:
            ctx.pop()
        assert 'error' in result


# ===========================================================================
# Pharmacy Return & Restock Tests
# ===========================================================================


class TestPharmacyReturn:
    """Tests for PharmacySaleService.process_pharmacy_return."""

    def _create_sale_item(self, app, test_tenant, test_medications):
        """Helper: create a sale with one item and return the sale_item."""
        from models.medication import PharmacySale, PharmacySaleItem, Medication

        patient_id = _make_patient(app, test_tenant)
        rx_id = _make_prescription(app, test_tenant, patient_id)
        med = test_medications[0]

        ctx = _tenant_ctx(app, test_tenant)
        try:
            result = PharmacySaleService.create_sale(
                prescription_id=rx_id,
                dispensed_by=_make_user(app, test_tenant).id,
                items=[{'medication_id': med.id, 'quantity': 2, 'unit_price': 10.0}],
                tenant_id=test_tenant.id,
            )
        finally:
            ctx.pop()

        sale = db.session.get(PharmacySale, result['sale_id'])
        sale_item = (
            db.session.execute(
                select(PharmacySaleItem).filter_by(sale_id=sale.id)
            )
            .scalars()
            .first()
        )
        # Capture stock AFTER the sale has decremented it
        med_after_sale = db.session.get(Medication, med.id)
        return sale_item, med_after_sale, med_after_sale.stock_quantity

    def test_return_restock_increases_stock(self, app, test_tenant, test_medications):
        """RESTOCK disposition should increment medication stock."""
        from models.medication import PharmacyReturn, Medication

        sale_item, med, post_sale_stock = self._create_sale_item(
            app, test_tenant, test_medications
        )

        ctx = _tenant_ctx(app, test_tenant)
        try:
            result = PharmacySaleService.process_pharmacy_return(
                sale_item_id=sale_item.id,
                quantity=1,
                disposition='RESTOCK',
                reason='Patient returned item',
                user_id=_make_user(app, test_tenant).id,
                tenant_id=test_tenant.id,
            )
        finally:
            ctx.pop()

        assert 'error' not in result
        assert result['disposition'] == 'RESTOCK'

        med_after = db.session.get(Medication, med.id)
        assert med_after.stock_quantity == post_sale_stock + 1

        # Verify PharmacyReturn log exists
        return_log = (
            db.session.execute(
                select(PharmacyReturn).filter_by(sale_item_id=sale_item.id)
            )
            .scalars()
            .first()
        )
        assert return_log is not None
        assert return_log.disposition == 'RESTOCK'
        assert return_log.quantity == 1

    def test_return_discard_does_not_increase_stock(self, app, test_tenant, test_medications):
        """DISCARD disposition should NOT increment medication stock."""
        from models.medication import PharmacyReturn, Medication

        sale_item, med, post_sale_stock = self._create_sale_item(
            app, test_tenant, test_medications
        )

        ctx = _tenant_ctx(app, test_tenant)
        try:
            result = PharmacySaleService.process_pharmacy_return(
                sale_item_id=sale_item.id,
                quantity=1,
                disposition='DISCARD',
                reason='Expired item discarded',
                user_id=_make_user(app, test_tenant).id,
                tenant_id=test_tenant.id,
            )
        finally:
            ctx.pop()

        assert 'error' not in result
        assert result['disposition'] == 'DISCARD'

        med_after = db.session.get(Medication, med.id)
        assert med_after.stock_quantity == post_sale_stock

        # Verify PharmacyReturn log exists with DISCARD disposition
        return_log = (
            db.session.execute(
                select(PharmacyReturn).filter_by(sale_item_id=sale_item.id)
            )
            .scalars()
            .first()
        )
        assert return_log is not None
        assert return_log.disposition == 'DISCARD'

    def test_return_exceeds_max_returnable(self, app, test_tenant, test_medications):
        """Returning more than sold should return an error."""
        sale_item, med, post_sale_stock = self._create_sale_item(
            app, test_tenant, test_medications
        )

        ctx = _tenant_ctx(app, test_tenant)
        try:
            result = PharmacySaleService.process_pharmacy_return(
                sale_item_id=sale_item.id,
                quantity=999,
                disposition='RESTOCK',
                reason='Too many',
                user_id=_make_user(app, test_tenant).id,
                tenant_id=test_tenant.id,
            )
        finally:
            ctx.pop()

        assert 'error' in result
