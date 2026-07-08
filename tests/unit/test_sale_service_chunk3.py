"""Unit tests for PharmacySaleService – create_sale, void_sale, get_prescription_status.

Chunk 3: commission/options, final-commit failure, and basic CRUD paths.
"""
import pytest
from unittest.mock import patch, MagicMock

from services.pharmacy_sale_service import PharmacySaleService
from app.shared.enums import PrescriptionState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_prescription(app, test_tenant, patient_id, status='active'):
    """Insert a minimal Prescription row and return its id."""
    from models.medication import Prescription
    from app.extensions import db

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
    from models.patient import Patient
    from app.extensions import db

    p = Patient(
        tenant_id=test_tenant.id,
        first_name='Test',
        last_name='Patient',
        gender='M',
    )
    db.session.add(p)
    db.session.commit()
    return p.id


# ===========================================================================
# TestCreateSaleCommissionAndOptions
# ===========================================================================

class TestCreateSaleCommissionAndOptions:
    """Tests for PharmacySaleService.create_sale."""

    # -- success paths ------------------------------------------------------

    def test_create_sale_basic(self, app, test_tenant):
        """Happy-path: single item sale commits and returns sale_id + total."""
        patient_id = _make_patient(app, test_tenant)
        rx_id = _make_prescription(app, test_tenant, patient_id)

        items = [{'medication_id': 1, 'quantity': 2, 'unit_price': 10.0}]
        result = PharmacySaleService.create_sale(
            prescription_id=rx_id,
            dispensed_by=1,
            items=items,
            tenant_id=test_tenant.id,
        )

        assert 'sale_id' in result
        assert result['total_amount'] == 20.0

    def test_create_sale_multiple_items(self, app, test_tenant):
        """Multi-item sale: total is the sum of qty * unit_price for each."""
        patient_id = _make_patient(app, test_tenant)
        rx_id = _make_prescription(app, test_tenant, patient_id)

        items = [
            {'medication_id': 1, 'quantity': 2, 'unit_price': 10.0},
            {'medication_id': 2, 'quantity': 1, 'unit_price': 5.50},
        ]
        result = PharmacySaleService.create_sale(
            prescription_id=rx_id,
            dispensed_by=1,
            items=items,
            tenant_id=test_tenant.id,
        )

        assert result['total_amount'] == pytest.approx(25.50)

    def test_create_sale_prescription_marked_dispensed(self, app, test_tenant):
        """After a successful sale the prescription status should be DISPENSED."""
        from models.medication import Prescription
        from app.extensions import db

        patient_id = _make_patient(app, test_tenant)
        rx_id = _make_prescription(app, test_tenant, patient_id)
        items = [{'medication_id': 1, 'quantity': 1, 'unit_price': 8.0}]

        PharmacySaleService.create_sale(
            prescription_id=rx_id,
            dispensed_by=1,
            items=items,
            tenant_id=test_tenant.id,
        )

        rx = Prescription.query.get(rx_id)
        assert rx.status == PrescriptionState.DISPENSED

    def test_create_sale_commission_fields(self, app, test_tenant):
        """Sale row gets correct tenant_id and sale_number prefix."""
        patient_id = _make_patient(app, test_tenant)
        rx_id = _make_prescription(app, test_tenant, patient_id)
        items = [{'medication_id': 1, 'quantity': 1, 'unit_price': 4.0}]

        result = PharmacySaleService.create_sale(
            prescription_id=rx_id,
            dispensed_by=1,
            items=items,
            tenant_id=test_tenant.id,
        )

        from models.medication import PharmacySale
        sale = PharmacySale.query.get(result['sale_id'])
        assert sale.tenant_id == test_tenant.id
        assert sale.sale_number.startswith('SALE-')

    # -- error paths --------------------------------------------------------

    def test_create_sale_prescription_not_found(self, app, test_tenant):
        """When prescription_id doesn't exist, return an error dict."""
        result = PharmacySaleService.create_sale(
            prescription_id=999_999,
            dispensed_by=1,
            items=[],
            tenant_id=test_tenant.id,
        )
        assert 'error' in result

    def test_create_sale_final_commit_failure(self, app, test_tenant):
        """When db.session.commit() raises, RuntimeError should propagate."""
        patient_id = _make_patient(app, test_tenant)
        rx_id = _make_prescription(app, test_tenant, patient_id)
        items = [{'medication_id': 1, 'quantity': 1, 'unit_price': 10.0}]

        with patch('services.pharmacy_sale_service.db') as mock_db:
            mock_db.session.commit.side_effect = Exception('db down')

            with pytest.raises(RuntimeError, match='final commit fail'):
                PharmacySaleService.create_sale(
                    prescription_id=rx_id,
                    dispensed_by=1,
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
            dispensed_by=1,
            items=[],
            tenant_id=test_tenant.id,
        )

        assert result['total_amount'] == 0

    def test_create_sale_uses_g_tenant_when_none(self, app, test_tenant):
        """When tenant_id is None the service should pick it up from g."""
        from flask import g

        patient_id = _make_patient(app, test_tenant)
        rx_id = _make_prescription(app, test_tenant, patient_id)
        items = [{'medication_id': 1, 'quantity': 1, 'unit_price': 3.0}]

        g.tenant_id = test_tenant.id
        try:
            result = PharmacySaleService.create_sale(
                prescription_id=rx_id,
                dispensed_by=1,
                items=items,
                # tenant_id intentionally omitted → defaults to g.tenant_id
            )
        finally:
            g.pop('tenant_id', None)

        assert 'sale_id' in result


# ===========================================================================
# void_sale tests (bonus – consistency with commit-failure guard)
# ===========================================================================

class TestVoidSale:
    """Tests for PharmacySaleService.void_sale."""

    def _create_sale(self, app, test_tenant):
        """Helper: create a real sale and return its id."""
        from models.medication import PharmacySale
        from app.extensions import db

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
        result = PharmacySaleService.void_sale(sale_id, reason='test')
        assert result['status'] == PrescriptionState.CANCELLED

    def test_void_sale_not_found(self, app, test_tenant):
        result = PharmacySaleService.void_sale(999_999)
        assert 'error' in result    def test_void_sale_commit_failure(self, app, test_tenant):
        sale_id = self._create_sale(app, test_tenant)

        with patch('services.pharmacy_sale_service.db') as mock_db:
            # Let the real query run to find the sale, but mock commit to fail
            from models.medication import PharmacySale
            sale_obj = PharmacySale.query.get(sale_id)
            mock_db.session.query.return_value.filter.return_value.filter.return_value.first.return_value = sale_obj
            mock_db.session.commit.side_effect = Exception('db down')

            with pytest.raises(RuntimeError, match='final commit fail'):
                PharmacySaleService.void_sale(sale_id)


# ===========================================================================
# get_prescription_status tests
# ===========================================================================

class TestGetPrescriptionStatus:
    """Tests for PharmacySaleService.get_prescription_status."""

    def test_prescription_status_success(self, app, test_tenant):
        patient_id = _make_patient(app, test_tenant)
        rx_id = _make_prescription(app, test_tenant, patient_id)

        result = PharmacySaleService.get_prescription_status(
            prescription_id=rx_id,
        )
        assert result['prescription_id'] == rx_id
        assert result['status'] == 'active'

    def test_prescription_status_not_found(self, app, test_tenant):
        result = PharmacySaleService.get_prescription_status(
            prescription_id=999_999,
        )
        assert 'error' in result
