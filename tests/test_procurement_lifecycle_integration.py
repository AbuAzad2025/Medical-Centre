"""Integration tests — full PO lifecycle through the REAL inventory ledger."""

import pytest


@pytest.fixture()
def _lifecycle_env(app, rollback_db, db, test_tenant):
    """Supplier + zero-stock medication inside a rolled-back transaction."""
    import uuid

    from models.medication import Medication, Supplier

    tag = uuid.uuid4().hex[:6]
    supplier = Supplier(tenant_id=test_tenant.id, name=f'Supp-Life-{tag}', is_active=True)
    db.session.add(supplier)
    db.session.flush()

    med = Medication(
        tenant_id=test_tenant.id,
        trade_name=f'M-Life-{tag}',
        scientific_name=f'S-Life-{tag}',
        dosage_form='tablet',
        strength='500mg',
        price=2.5,
        stock_quantity=0,
        minimum_stock=3,
        category='general',
        is_active=True,
    )
    db.session.add(med)
    db.session.commit()

    return {
        'supplier_id': supplier.id,
        'medication_id': med.id,
        'tenant_id': test_tenant.id,
        'tenant': test_tenant,
    }


class TestProcurementLifecycleIntegration:
    def test_receive_once_stock_ledger_and_idempotency(self, app, db, _lifecycle_env):
        with app.test_request_context():
            from tests.tenant_context import bind_tenant_on_g

            bind_tenant_on_g(_lifecycle_env['tenant'], db_session=db.session)

            from sqlalchemy import select

            from app.modules.workflows.stock_models import StockMovement
            from models.medication import Medication, MedicationPurchase
            from services.procurement_service import ProcurementError, ProcurementService

            po = ProcurementService.create_purchase_order(
                supplier_id=_lifecycle_env['supplier_id'],
                items=[
                    {
                        'medication_id': _lifecycle_env['medication_id'],
                        'quantity': 7,
                        'purchase_price': 2.0,
                        'batch_number': 'LIFE-001',
                    }
                ],
                created_by=1,
            )

            result = ProcurementService.receive_purchase(po['po_id'], received_by=1)
            assert result['qty_received'] == 7
            assert result['medication_id'] == _lifecycle_env['medication_id']

            db.session.expire_all()
            med = db.session.get(Medication, _lifecycle_env['medication_id'])
            assert med.stock_quantity == 7

            movements = (
                db.session.execute(
                    select(StockMovement).filter_by(
                        medication_id=_lifecycle_env['medication_id'],
                        reference_type='MedicationPurchase',
                        reference_id=po['po_id'],
                    )
                )
                .scalars()
                .all()
            )
            assert len(movements) == 1
            assert movements[0].movement_type == 'purchase'
            assert movements[0].quantity == 7
            assert movements[0].before_quantity == 0
            assert movements[0].after_quantity == 7

            mp = db.session.get(MedicationPurchase, po['po_id'])
            assert mp.remaining_quantity == 0

            with pytest.raises(ProcurementError, match='already_received'):
                ProcurementService.receive_purchase(po['po_id'], received_by=1)

            db.session.expire_all()
            med_after = db.session.get(Medication, _lifecycle_env['medication_id'])
            assert med_after.stock_quantity == 7

            all_movements = (
                db.session.execute(
                    select(StockMovement).filter_by(medication_id=_lifecycle_env['medication_id'])
                )
                .scalars()
                .all()
            )
            assert len(all_movements) == 1

    def test_receive_invalid_movement_type_rejected_by_ledger(self, app, db, _lifecycle_env):
        with app.test_request_context():
            from tests.tenant_context import bind_tenant_on_g

            bind_tenant_on_g(_lifecycle_env['tenant'], db_session=db.session)

            from services.inventory_ledger_service import InventoryLedgerService

            assert 'purchase_receipt' not in InventoryLedgerService.MOVEMENT_TYPES
            assert 'purchase' in InventoryLedgerService.MOVEMENT_TYPES
