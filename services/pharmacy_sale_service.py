"""
PharmacySaleService - manages pharmacy sales and dispensing workflow
"""
from datetime import datetime, timezone
from flask import g
from app.extensions import db
from app.shared.enums import PrescriptionState


class PharmacySaleService:
    """Manages pharmacy sale processing and dispensing."""

    @staticmethod
    def create_sale(prescription_id: int, dispensed_by: int, items: list[dict], tenant_id: int | None = None) -> dict:
        from models.medication import Prescription, PrescriptionItem, PharmacySale, PharmacySaleItem
        tenant_id = tenant_id or getattr(g, 'tenant_id', None)
        prescription = Prescription.query.get(prescription_id)
        if not prescription:
            return {"error": "Prescription not found"}
        sale = PharmacySale(
            tenant_id=tenant_id,
            patient_id=prescription.patient_id,
            sale_number=f"SALE-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            total_amount=0,
            status='completed',
        )
        db.session.add(sale)
        db.session.flush()
        total = 0
        for item in items:
            sale_item = PharmacySaleItem(
                tenant_id=tenant_id,
                sale_id=sale.id,
                medication_id=item.get('medication_id'),
                quantity=item.get('quantity', 1),
                unit_price=item.get('unit_price', 0),
            )
            db.session.add(sale_item)
            total += item.get('quantity', 1) * item.get('unit_price', 0)
        sale.total_amount = total
        prescription.status = PrescriptionState.DISPENSED
        db.session.commit()
        return {"sale_id": sale.id, "total_amount": total}

    @staticmethod
    def void_sale(sale_id: int, reason: str = "") -> dict:
        from models.medication import PharmacySale
        sale = PharmacySale.query.get(sale_id)
        if not sale:
            return {"error": "Sale not found"}
        sale.status = PrescriptionState.CANCELLED
        db.session.commit()
        return {"sale_id": sale.id, "status": PrescriptionState.CANCELLED}

    @staticmethod
    def get_prescription_status(prescription_id: int) -> dict:
        from models.medication import Prescription, PharmacySale
        prescription = Prescription.query.get(prescription_id)
        if not prescription:
            return {"error": "Prescription not found"}
        sales = PharmacySale.query.filter_by(prescription_id=prescription_id).all()
        return {
            "prescription_id": prescription_id,
            "status": prescription.status,
            "dispensed_count": len(sales),
        }
