"""
ProcurementService — purchase order lifecycle (create→approve→receive→stock).

Uses existing Supplier + MedicationPurchase models.  On receipt, integrates
with PharmacyStockService to increment stock and create ledger entries.
"""

import logging
from datetime import UTC, datetime

from flask import g
from sqlalchemy import select

from app.extensions import db
from utils.db_safety import safe_commit

logger = logging.getLogger(__name__)


class ProcurementError(Exception):
    pass


class ProcurementService:
    @staticmethod
    def create_purchase_order(supplier_id: int, items: list[dict], created_by: int) -> dict:
        """Create a purchase order with line items.

        items = [{'medication_id': int, 'quantity': int, 'purchase_price': float,
                  'batch_number': str, 'expiry_date': 'YYYY-MM-DD' (optional)}]
        Returns {'po_id': int, 'total': float, 'item_count': int}
        """
        from models.medication import MedicationPurchase, Supplier

        if not items:
            raise ProcurementError('no_items')

        supplier = db.session.get(Supplier, supplier_id)
        if not supplier or not supplier.is_active:
            raise ProcurementError('supplier_not_found')

        total = 0.0
        records = []
        for item in items:
            med_id = item.get('medication_id')
            qty = int(item.get('quantity', 0))
            price = float(item.get('purchase_price', 0))
            batch = item.get('batch_number', '')

            if not med_id or qty <= 0 or not batch:
                raise ProcurementError('invalid_item')

            mp = MedicationPurchase(
                tenant_id=getattr(g, 'tenant_id', None),
                supplier_id=supplier_id,
                medication_id=med_id,
                batch_number=batch,
                quantity=qty,
                remaining_quantity=qty,
                purchase_price=price,
                expiry_date=item.get('expiry_date'),
                purchase_date=datetime.now(UTC).date(),
                created_by=created_by,
            )
            db.session.add(mp)
            records.append(mp)
            total += qty * price

        safe_commit(db.session, error_message='Failed to create PO', reraise=True)
        return {
            'po_id': records[0].id if records else None,
            'total': round(total, 2),
            'item_count': len(records),
            'supplier': supplier.name,
        }

    @staticmethod
    def receive_purchase(purchase_id: int, received_by: int) -> dict:
        """Receive a purchase → increments medication stock.

        Uses PharmacyStockService.adjust_stock for ledger consistency.
        """
        from models.medication import MedicationPurchase
        from services.inventory_ledger_service import InventoryLedgerService

        mp = db.session.get(MedicationPurchase, purchase_id)
        if not mp:
            raise ProcurementError('purchase_not_found')
        if mp.remaining_quantity <= 0:
            raise ProcurementError('already_received')

        received_qty = mp.remaining_quantity
        InventoryLedgerService.record_movement(
            medication_id=mp.medication_id,
            quantity_change=received_qty,
            movement_type='purchase_receipt',
            reference_type='MedicationPurchase',
            reference_id=mp.id,
            performed_by=received_by,
        )

        # Update medication stock
        med = getattr(mp, 'medication', None)
        if med:
            med.stock_quantity = (med.stock_quantity or 0) + received_qty

        mp.remaining_quantity = 0
        safe_commit(db.session, error_message='Failed to receive purchase', reraise=True)

        return {
            'purchase_id': mp.id,
            'medication_id': mp.medication_id,
            'qty_received': received_qty,
        }

    @staticmethod
    def list_purchases(tenant_id: int | None = None) -> list:
        """List all purchases for current tenant."""
        from models.medication import MedicationPurchase

        q = select(MedicationPurchase).order_by(MedicationPurchase.created_at.desc())
        tid = tenant_id or getattr(g, 'tenant_id', None)
        if tid:
            q = q.filter_by(tenant_id=tid)
        return list(db.session.execute(q).scalars().all())

    @staticmethod
    def get_supplier_summary(supplier_id: int) -> dict:
        """Summary of purchases per supplier."""
        from models.medication import MedicationPurchase, Supplier

        supplier = db.session.get(Supplier, supplier_id)
        if not supplier:
            raise ProcurementError('supplier_not_found')

        purchases = (
            db.session.execute(select(MedicationPurchase).filter_by(supplier_id=supplier_id))
            .scalars()
            .all()
        )
        total_value = sum(float(p.purchase_price or 0) * p.quantity for p in purchases)
        return {
            'supplier': supplier.name,
            'purchase_count': len(purchases),
            'total_value': round(total_value, 2),
        }
