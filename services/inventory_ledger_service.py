"""
InventoryLedgerService — mandatory stock ledger for every movement
"""
from sqlalchemy import select
from flask import g
from app.extensions import db
from services.feature_gate_service import require_module


class InventoryLedgerService:
    MOVEMENT_TYPES = ('purchase', 'dispense', 'sale', 'return', 'adjustment', 'transfer', 'waste')

    # Movement types that increase stock (all others decrease it)
    INBOUND_TYPES = ('purchase', 'return', 'adjustment')

    @staticmethod
    @require_module('inventory')
    def record_movement(
        medication_id: int,
        movement_type: str,
        quantity: int,
        reference_type: str = "",
        reference_id: int | None = None,
        notes: str = "",
        tenant_id: int | None = None,
    ) -> dict:
        if movement_type not in InventoryLedgerService.MOVEMENT_TYPES:
            raise ValueError(f"Invalid movement type: {movement_type}")
        if quantity < 0:
            raise ValueError("quantity must be a positive integer; direction is derived from movement_type")
        # Delegates to PharmacyStockService, the canonical writer that keeps
        # Medication.stock_quantity and the stock_movements ledger consistent.
        from app.modules.workflows.pharmacy import PharmacyStockService

        sign = 1 if movement_type in InventoryLedgerService.INBOUND_TYPES else -1
        performed_by = None
        user = getattr(g, 'current_user', None)
        if user is not None and getattr(user, 'id', None):
            performed_by = user.id

        PharmacyStockService.adjust_stock(
            medication_id=medication_id,
            quantity_change=sign * quantity,
            movement_type=movement_type,
            reference_type=reference_type or None,
            reference_id=reference_id,
            performed_by=performed_by,
            notes=notes or None,
        )
        return {"type": movement_type, "quantity": sign * quantity}

    @staticmethod
    @require_module('inventory')
    def current_stock(medication_id: int, tenant_id: int | None = None) -> int:
        tid = tenant_id or getattr(g, 'tenant_id', None)
        from app.modules.workflows.stock_models import StockMovement
        movements = db.session.execute(select(StockMovement).filter_by(
            medication_id=medication_id, tenant_id=tid
        )).scalars().all()
        # StockMovement.quantity is signed (negative for outflow), so the
        # running balance is the plain sum of all recorded movements.
        return max(0, sum(m.quantity for m in movements))

    @staticmethod
    @require_module('inventory')
    def low_stock_alerts(threshold: int = 10, tenant_id: int | None = None) -> list:
        tid = tenant_id or getattr(g, 'tenant_id', None)
        from models.medication import Medication
        alerts = []
        medications = db.session.execute(select(Medication).filter_by(tenant_id=tid)).scalars().all()
        for med in medications:
            stock = InventoryLedgerService.current_stock(med.id, tid)
            min_stock = getattr(med, 'minimum_stock', threshold) or threshold
            if stock <= min_stock:
                alerts.append({
                    "medication_id": med.id,
                    "name": med.trade_name or med.scientific_name,
                    "current_stock": stock,
                    "minimum_stock": min_stock,
                })
        return alerts
