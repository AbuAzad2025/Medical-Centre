"""
InventoryLedgerService — mandatory stock ledger for every movement
"""
from datetime import datetime, timezone
from flask import g
from app.extensions import db


class InventoryLedgerService:
    MOVEMENT_TYPES = ('purchase', 'dispense', 'sale', 'return', 'adjustment', 'transfer', 'waste')

    @staticmethod
    def record_movement(
        medication_id: int,
        movement_type: str,
        quantity: int,
        reference_type: str = "",
        reference_id: int | None = None,
        notes: str = "",
        unit_cost: float | None = None,
        tenant_id: int | None = None,
    ) -> dict:
        if movement_type not in InventoryLedgerService.MOVEMENT_TYPES:
            raise ValueError(f"Invalid movement type: {movement_type}")
        tid = tenant_id or getattr(g, 'tenant_id', None)
        from app.modules.workflows.stock_models import StockMovement
        movement = StockMovement(
            tenant_id=tid,
            medication_id=medication_id,
            movement_type=movement_type,
            quantity=quantity,
            reference_type=reference_type,
            reference_id=reference_id,
            unit_cost=unit_cost,
            notes=notes,
            created_by=getattr(g, 'current_user', None) and g.current_user.id or None,
        )
        db.session.add(movement)
        db.session.commit()
        return {"id": movement.id, "type": movement_type, "quantity": quantity}

    @staticmethod
    def current_stock(medication_id: int, tenant_id: int | None = None) -> int:
        tid = tenant_id or getattr(g, 'tenant_id', None)
        from app.modules.workflows.stock_models import StockMovement
        movements = StockMovement.query.filter_by(
            medication_id=medication_id, tenant_id=tid
        ).all()
        stock = 0
        for m in movements:
            if m.movement_type in ('purchase', 'return', 'adjustment'):
                stock += m.quantity
            else:
                stock -= m.quantity
        return max(0, stock)

    @staticmethod
    def low_stock_alerts(threshold: int = 10, tenant_id: int | None = None) -> list:
        tid = tenant_id or getattr(g, 'tenant_id', None)
        from models.medication import Medication
        alerts = []
        medications = Medication.query.filter_by(tenant_id=tid).all()
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