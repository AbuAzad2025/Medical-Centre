"""
Prescription Service - Business logic for prescriptions and medications.
Extracted from routes/doctor/prescriptions.py and routes/medication_routes/.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app_factory import db
from sqlalchemy import and_, or_


class PrescriptionService:
    """Centralized prescription and medication business logic"""

    # ==================== DRUG INTERACTIONS ====================

    @staticmethod
    def check_interactions(medication_ids: list[int]) -> list[dict]:
        """Check for drug interactions between a list of medication IDs."""
        from models.medication import Medication
        from models.drug_interaction import DrugInteraction
        warnings = []
        try:
            med_ids_sorted = sorted({int(x) for x in medication_ids if x})
            pairs = []
            for i in range(len(med_ids_sorted)):
                for j in range(i + 1, len(med_ids_sorted)):
                    a = min(med_ids_sorted[i], med_ids_sorted[j])
                    b = max(med_ids_sorted[i], med_ids_sorted[j])
                    pairs.append((a, b))
            if pairs:
                conds = [and_(DrugInteraction.medication_a_id == a, DrugInteraction.medication_b_id == b) for a, b in pairs]
                rows = DrugInteraction.query.filter(DrugInteraction.is_active == True).filter(or_(*conds)).all()
                for row in rows:
                    a = Medication.query.get(row.medication_a_id)
                    b = Medication.query.get(row.medication_b_id)
                    a_name = a.trade_name if a else f"ID {row.medication_a_id}"
                    b_name = b.trade_name if b else f"ID {row.medication_b_id}"
                    warnings.append({
                        "a_id": row.medication_a_id, "b_id": row.medication_b_id,
                        "a_name": a_name, "b_name": b_name,
                        "severity": getattr(row, "severity", "unknown"),
                        "description": row.description or getattr(row, "interaction_type", f"تفاعل بين {a_name} و {b_name}"),
                    })
        except Exception:
            pass
        return warnings

    @staticmethod
    def check_patient_allergies(patient_id: int, medication_ids: list[int]) -> list[dict]:
        """Check if any medications conflict with patient allergies."""
        from models.patient import Patient, PatientAllergy
        from models.medication import Medication
        conflicts = []
        try:
            allergies = PatientAllergy.query.filter_by(patient_id=patient_id).all()
            if not allergies:
                return conflicts
            meds = Medication.query.filter(Medication.id.in_(medication_ids)).all()
            for med in meds:
                for allergy in allergies:
                    if (allergy.medication_id and allergy.medication_id == med.id) or \
                       (allergy.allergen_name and med.trade_name and allergy.allergen_name in med.trade_name):
                        conflicts.append({
                            "medication_id": med.id,
                            "medication_name": med.trade_name,
                            "allergen": allergy.allergen_name or allergy.allergen_type or "Unknown",
                            "severity": getattr(allergy, "severity", "warning"),
                        })
        except Exception:
            pass
        return conflicts

    # ==================== PRESCRIPTION CREATION ====================

    @staticmethod
    def create_prescription(
        patient_id: int, doctor_id: int, visit_id: int | None = None,
        tenant_id: int | None = None,
        items: list[dict] | None = None, notes: str | None = None,
        diagnosis: str | None = None,
        prescription_number: str | None = None
    ) -> tuple[bool, Any | str]:
        """Create a Prescription with PrescriptionItems.

        P2-002: The service resolves medication_id → Medication (formulary),
        computes unit_price/total_price from Medication.price, and ensures
        tenant scoping on both Prescription and PrescriptionItem rows.

        Item dict expected keys:
          medication_id (int), dosage (str), quantity (int),
          duration_days (int), instructions (str | None)
        """
        from models.medication import Medication, Prescription, PrescriptionItem
        try:
            prescription = Prescription(
                tenant_id=tenant_id,
                patient_id=patient_id,
                doctor_id=doctor_id,
                visit_id=visit_id,
                diagnosis=diagnosis,
                notes=notes,
                status="active",
                prescription_number=prescription_number or f"RX-{uuid.uuid4().hex[:8].upper()}",
            )
            db.session.add(prescription)
            db.session.flush()

            if items:
                for item_data in items:
                    med_id = item_data.get("medication_id")
                    if not med_id:
                        continue
                    med = Medication.query.get(med_id)
                    if not med:
                        db.session.rollback()
                        return False, f"Medication {med_id} not found"

                    item_qty = int(item_data.get("quantity", 1) or 1)
                    unit_price = med.price or Decimal('0')
                    total_price = unit_price * item_qty

                    item = PrescriptionItem(
                        tenant_id=tenant_id,
                        prescription_id=prescription.id,
                        medication_id=med.id,
                        dosage=item_data.get("dosage", ""),
                        quantity=item_qty,
                        duration_days=int(item_data.get("duration_days", 7) or 7),
                        instructions=item_data.get("instructions") or item_data.get("notes"),
                        unit_price=unit_price,
                        total_price=total_price,
                    )
                    db.session.add(item)

            prescription.calculate_total_cost()
            db.session.commit()
            return True, prescription
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating prescription: {str(e)}")
            return False, str(e)

    @staticmethod
    def get_active_prescriptions(patient_id: int) -> list:
        from models.medication import Prescription
        return Prescription.query.filter_by(
            patient_id=patient_id, status="active"
        ).order_by(Prescription.created_at.desc()).all()

    @staticmethod
    def get_prescriptions_by_doctor(doctor_id: int, limit: int = 50) -> list:
        from models.medication import Prescription
        return Prescription.query.filter_by(doctor_id=doctor_id).order_by(
            Prescription.created_at.desc()
        ).limit(limit).all()

    # ==================== MEDICATION INVENTORY ====================

    @staticmethod
    def get_low_stock_medications(limit: int = 10) -> list:
        from models.medication import Medication
        return Medication.query.filter(
            Medication.stock_quantity <= Medication.minimum_stock
        ).limit(limit).all()

    @staticmethod
    def search_medications(query: str) -> list:
        from models.medication import Medication
        return Medication.query.filter(
            or_(
                Medication.trade_name.ilike(f"%{query}%"),
                Medication.generic_name.ilike(f"%{query}%"),
            )
        ).order_by(Medication.trade_name).all()

    @staticmethod
    def update_stock(medication_id: int, quantity_change: float) -> bool:
        from models.medication import Medication
        try:
            med = Medication.query.get(medication_id)
            if not med:
                return False
            med.stock_quantity = (med.stock_quantity or 0) + quantity_change
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error updating medication stock: {str(e)}")
            return False

    # ==================== SUPPLY REQUESTS ====================

    @staticmethod
    def create_supply_request(
        medication_id: int, quantity: float, requested_by: int,
        notes: str | None = None
    ) -> Any | None:
        from models.medication import Medication
        from models.supply_request import MedicationSupplyRequest, MedicationSupplyRequestItem
        try:
            med = Medication.query.get(medication_id)
            if not med:
                return None
            request = MedicationSupplyRequest(
                medication_id=medication_id,
                quantity_requested=quantity,
                requested_by=requested_by,
                status="PENDING",
                notes=notes,
                created_at=datetime.now(timezone.utc),
            )
            db.session.add(request)
            db.session.flush()

            item = MedicationSupplyRequestItem(
                request_id=request.id,
                medication_id=medication_id,
                quantity=quantity,
            )
            db.session.add(item)
            db.session.commit()
            return request
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating supply request: {str(e)}")
            return None

    @staticmethod
    def get_supply_requests(status: str | None = None) -> list:
        from models.supply_request import MedicationSupplyRequest
        q = MedicationSupplyRequest.query
        if status:
            q = q.filter_by(status=status)
        return q.order_by(MedicationSupplyRequest.created_at.desc()).all()

    # ==================== NOTIFICATION ====================

    @staticmethod
    def notify_pharmacy_non_catalog(medication_name: str, doctor_name: str, visit_id: int) -> None:
        try:
            from services.notification_service import NotificationService
            NotificationService.send_notification(
                recipient_role="pharmacist",
                title="دواء خارج التصنيف",
                message=f"الطبيب {doctor_name} وصف دواء {medication_name} (خارج التصنيف) للزيارة #{visit_id}",
                notification_type="warning",
            )
        except Exception:
            pass

    # ==================== AUDIT ====================

    @staticmethod
    def get_medication(medication_id: int):
        from models.medication import Medication
        return Medication.query.get(medication_id)

    @staticmethod
    def get_prescription(prescription_id: int):
        from models.medication import Prescription
        return Prescription.query.get(prescription_id)

    @staticmethod
    def log_action(action: str, details: str, user_id: int | None = None) -> None:
        from models.audit_trail import AuditTrail
        try:
            log = AuditTrail(
                action=action, details=details,
                user_id=user_id, created_at=datetime.now(timezone.utc),
            )
            db.session.add(log)
            db.session.commit()
        except Exception:
            db.session.rollback()


# Singleton
prescription_service = PrescriptionService()
