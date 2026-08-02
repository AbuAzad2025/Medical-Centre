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
