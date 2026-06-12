"""
PharmacyStockService — stock movement ledger
"""
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional
from app.extensions import db

class StockMovementType(str, Enum):
    PURCHASE = "purchase"
    SALE = "sale"
    RETURN = "return"
    ADJUSTMENT = "adjustment"
    EXPIRED = "expired"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"


class PharmacyStockService:
    """All stock changes MUST go through this service to maintain audit trail."""

    @staticmethod
    def adjust_stock(medication_id: int, quantity_change: int, movement_type: str,
                       reference_type: Optional[str] = None, reference_id: Optional[int] = None,
                       performed_by: Optional[int] = None, notes: Optional[str] = None,
                       batch_number: Optional[str] = None, expiry_date: Optional[str] = None) -> None:
        from models.medication import Medication
        from app.modules.workflows.stock_models import StockMovement

        med = db.session.get(Medication, medication_id)
        if not med:
            raise ValueError("Medication not found")

        # Prevent negative stock unless it's an adjustment/correction
        if quantity_change < 0 and movement_type not in (StockMovementType.ADJUSTMENT, StockMovementType.EXPIRED):
            if med.stock_quantity + quantity_change < 0:
                raise ValueError("Insufficient stock")

        med.stock_quantity = max(0, med.stock_quantity + quantity_change)
        med.updated_at = datetime.now(timezone.utc)

        movement = StockMovement(
            medication_id=medication_id,
            movement_type=movement_type,
            quantity=quantity_change,
            before_quantity=med.stock_quantity - quantity_change,
            after_quantity=med.stock_quantity,
            reference_type=reference_type,
            reference_id=reference_id,
            performed_by=performed_by,
            notes=notes,
            batch_number=batch_number,
            expiry_date=expiry_date,
        )
        db.session.add(med)
        db.session.add(movement)

    @staticmethod
    def dispense_prescription_item(prescription_item_id: int, dispensed_qty: int,
                                    performed_by: Optional[int] = None) -> None:
        from models.medication import PrescriptionItem
        pi = db.session.get(PrescriptionItem, prescription_item_id)
        if not pi:
            raise ValueError("PrescriptionItem not found")
        if pi.dispensed_quantity + dispensed_qty > pi.quantity:
            raise ValueError("Cannot dispense more than prescribed")

        PharmacyStockService.adjust_stock(
            medication_id=pi.medication_id,
            quantity_change=-dispensed_qty,
            movement_type=StockMovementType.SALE,
            reference_type="PrescriptionItem",
            reference_id=pi.id,
            performed_by=performed_by,
            notes=f"Dispensed for prescription item {pi.id}"
        )
        pi.dispensed_quantity = pi.dispensed_quantity + dispensed_qty
        pi.dispensed_at = datetime.now(timezone.utc)
        db.session.add(pi)
