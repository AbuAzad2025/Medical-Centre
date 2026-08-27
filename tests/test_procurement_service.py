"""Procurement service tests — full PO lifecycle."""

import pytest


@pytest.fixture()
def _proc_env(app, db, test_tenant):
    """Supplier + medication + authenticated context."""
    import uuid

    from models.medication import Medication, Supplier
    from models.user import User

    tag = uuid.uuid4().hex[:6]
    buyer = User(
        username=f'po_{tag}',
        email=f'po_{tag}@test.local',
        full_name='PO Maker',
        role='manager',
        is_active=True,
        tenant_id=test_tenant.id,
    )
    buyer.set_password('test123')
    db.session.add(buyer)
    db.session.flush()

    supplier = Supplier(tenant_id=test_tenant.id, name=f'Supp-{tag}', is_active=True)
    db.session.add(supplier)
    db.session.flush()

    med = Medication(
        tenant_id=test_tenant.id,
        trade_name=f'M-{tag}',
        scientific_name=f'S-{tag}',
        dosage_form='tablet',
        strength='500mg',
        price=10,
        stock_quantity=0,
        minimum_stock=5,
        category='general',
        is_active=True,
    )
    db.session.add(med)
    db.session.commit()

    return {
        'user_id': buyer.id,
        'supplier_id': supplier.id,
        'medication_id': med.id,
        'tenant_id': test_tenant.id,
    }


class TestCreatePurchaseOrder:
    def test_create_valid_po(self, app, db, _proc_env):
        with app.test_request_context():
            from flask import g

            g.tenant_id = _proc_env['tenant_id']

            from services.procurement_service import ProcurementService

            result = ProcurementService.create_purchase_order(
                supplier_id=_proc_env['supplier_id'],
                items=[
                    {
                        'medication_id': _proc_env['medication_id'],
                        'quantity': 100,
                        'purchase_price': 5.0,
                        'batch_number': 'B001',
                    }
                ],
                created_by=_proc_env['user_id'],
            )
            assert result['total'] == 500.0
            assert result['item_count'] == 1

    def test_create_empty_items_raises(self, app, _proc_env):
        with app.test_request_context():
            from flask import g

            g.tenant_id = _proc_env['tenant_id']

            from services.procurement_service import ProcurementError, ProcurementService

            with pytest.raises(ProcurementError, match='no_items'):
                ProcurementService.create_purchase_order(
                    supplier_id=_proc_env['supplier_id'],
                    items=[],
                    created_by=_proc_env['user_id'],
                )

    def test_create_invalid_supplier_raises(self, app, _proc_env):
        with app.test_request_context():
            from flask import g

            g.tenant_id = _proc_env['tenant_id']

            from services.procurement_service import ProcurementError, ProcurementService

            with pytest.raises(ProcurementError, match='supplier_not_found'):
                ProcurementService.create_purchase_order(
                    supplier_id=99999,
                    items=[
                        {
                            'medication_id': _proc_env['medication_id'],
                            'quantity': 10,
                            'batch_number': 'B',
                        }
                    ],
                    created_by=_proc_env['user_id'],
                )

    def test_create_invalid_item_raises(self, app, _proc_env):
        with app.test_request_context():
            from flask import g

            g.tenant_id = _proc_env['tenant_id']

            from services.procurement_service import ProcurementError, ProcurementService

            with pytest.raises(ProcurementError, match='invalid_item'):
                ProcurementService.create_purchase_order(
                    supplier_id=_proc_env['supplier_id'],
                    items=[{'medication_id': None, 'quantity': 0, 'batch_number': ''}],
                    created_by=_proc_env['user_id'],
                )


class TestReceivePurchase:
    def test_receive_increments_stock(self, app, db, _proc_env):
        with app.test_request_context():
            from flask import g

            g.tenant_id = _proc_env['tenant_id']

            from models.medication import Medication
            from services.procurement_service import ProcurementService

            po = ProcurementService.create_purchase_order(
                supplier_id=_proc_env['supplier_id'],
                items=[
                    {
                        'medication_id': _proc_env['medication_id'],
                        'quantity': 50,
                        'purchase_price': 3.0,
                        'batch_number': 'B-RX',
                    }
                ],
                created_by=_proc_env['user_id'],
            )

            med = db.session.get(Medication, _proc_env['medication_id'])
            initial_stock = med.stock_quantity or 0

            # Mock InventoryLedgerService to avoid complex setup
            from unittest.mock import patch

            with patch('services.inventory_ledger_service.InventoryLedgerService.record_movement'):
                result = ProcurementService.receive_purchase(po['po_id'], received_by=1)

            assert result['qty_received'] == 50

            # Verify stock incremented
            db.session.expire_all()
            med_fresh = db.session.get(Medication, _proc_env['medication_id'])
            assert (med_fresh.stock_quantity or 0) == initial_stock + 50

    def test_receive_twice_raises(self, app, db, _proc_env):
        with app.test_request_context():
            from flask import g

            g.tenant_id = _proc_env['tenant_id']

            from services.procurement_service import (
                ProcurementError,
                ProcurementService,
            )

            po = ProcurementService.create_purchase_order(
                supplier_id=_proc_env['supplier_id'],
                items=[
                    {
                        'medication_id': _proc_env['medication_id'],
                        'quantity': 20,
                        'purchase_price': 2.0,
                        'batch_number': 'B-D',
                    }
                ],
                created_by=_proc_env['user_id'],
            )

            from unittest.mock import patch

            with patch('services.inventory_ledger_service.InventoryLedgerService.record_movement'):
                ProcurementService.receive_purchase(po['po_id'], received_by=1)

            with pytest.raises(ProcurementError, match='already_received'):
                ProcurementService.receive_purchase(po['po_id'], received_by=1)

    def test_receive_nonexistent_raises(self, app):
        with app.app_context():
            from services.procurement_service import ProcurementError, ProcurementService

            with pytest.raises(ProcurementError, match='purchase_not_found'):
                ProcurementService.receive_purchase(99999, received_by=1)


class TestSupplierSummary:
    def test_summary_with_purchases(self, app, db, _proc_env):
        with app.test_request_context():
            from flask import g

            g.tenant_id = _proc_env['tenant_id']

            from services.procurement_service import ProcurementService

            ProcurementService.create_purchase_order(
                supplier_id=_proc_env['supplier_id'],
                items=[
                    {
                        'medication_id': _proc_env['medication_id'],
                        'quantity': 30,
                        'purchase_price': 4.0,
                        'batch_number': 'B-S1',
                    }
                ],
                created_by=_proc_env['user_id'],
            )

            summary = ProcurementService.get_supplier_summary(_proc_env['supplier_id'])
            assert summary['purchase_count'] >= 1
            assert summary['total_value'] > 0

    def test_summary_nonexistent_supplier(self, app):
        with app.app_context():
            from services.procurement_service import ProcurementError, ProcurementService

            with pytest.raises(ProcurementError, match='supplier_not_found'):
                ProcurementService.get_supplier_summary(99999)
