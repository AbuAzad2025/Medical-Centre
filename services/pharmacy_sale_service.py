"""
PharmacySaleService - manages pharmacy sales and dispensing workflow
"""
from datetime import datetime, timezone
from uuid import uuid4
from flask import g
from app.extensions import db
from app.shared.enums import PrescriptionState
from utils.db_safety import safe_commit


class PharmacySaleService:
    """Manages pharmacy sale processing and dispensing."""

    @staticmethod
    def create_sale(prescription_id: int, dispensed_by: int, items: list[dict], tenant_id: int | None = None) -> dict:
        from models.medication import Prescription, PharmacySale, PharmacySaleItem, Medication
        tenant_id = tenant_id or getattr(g, 'tenant_id', None)
        prescription = Prescription.query.filter(Prescription.id == prescription_id, Prescription.tenant_id == tenant_id).first()
        if not prescription:
            return {"error": "Prescription not found"}
        sale = PharmacySale(
            tenant_id=tenant_id,
            patient_id=prescription.patient_id,
            sale_number=f"SALE-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6]}",
            total_amount=0,
            status='completed',
        )
        db.session.add(sale)
        db.session.flush()
        total = 0
        for item in items:
            med_id = item.get('medication_id')
            if not med_id:
                safe_commit(db.session, error_message="medication_id required")
                return {"error": "medication_id required"}
            med = Medication.query.filter(
                Medication.id == med_id,
                Medication.tenant_id == tenant_id,
            ).first()
            if not med:
                safe_commit(db.session, error_message=f"Medication {med_id} not found")
                return {"error": f"Medication {med_id} not found"}
            qty = item.get('quantity', 1)
            unit_price = item.get('unit_price', 0)
            line_total = qty * unit_price
            sale_item = PharmacySaleItem(
                tenant_id=tenant_id,
                sale_id=sale.id,
                medication_id=med_id,
                medication_name=med.trade_name or med.scientific_name or str(med_id),
                quantity=qty,
                unit_price=unit_price,
                total_price=line_total,
            )
            db.session.add(sale_item)
            total += line_total
        sale.total_amount = total
        prescription.status = PrescriptionState.DISPENSED
        safe_commit(db.session, error_message="final commit fail", reraise=True)
        return {"sale_id": sale.id, "total_amount": total}

    @staticmethod
    def void_sale(sale_id: int, reason: str = "") -> dict:
        from models.medication import PharmacySale
        sale = PharmacySale.query.filter(PharmacySale.id == sale_id, PharmacySale.tenant_id == getattr(g, 'tenant_id', None)).first()
        if not sale:
            return {"error": "Sale not found"}
        sale.status = PrescriptionState.CANCELLED
        safe_commit(db.session, error_message="final commit fail", reraise=True)
        return {"sale_id": sale.id, "status": PrescriptionState.CANCELLED}

    @staticmethod
    def get_prescription_status(prescription_id: int) -> dict:
        from models.medication import Prescription, PharmacySale
        prescription = Prescription.query.filter(Prescription.id == prescription_id, Prescription.tenant_id == getattr(g, 'tenant_id', None)).first()
        if not prescription:
            return {"error": "Prescription not found"}
        sales = PharmacySale.query.filter_by(prescription_id=prescription_id).all()
        return {
            "prescription_id": prescription_id,
            "status": prescription.status,
            "dispensed_count": len(sales),
        }
