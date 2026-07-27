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

from flask import g
from app.extensions import db
from utils.db_safety import safe_commit
from sqlalchemy import and_, or_, select
from services.feature_gate_service import require_module


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
                rows = db.session.execute(select(DrugInteraction).filter(DrugInteraction.is_active == True).filter(or_(*conds))).scalars().all()
                for row in rows:
                    a = db.session.execute(select(Medication).filter(Medication.id == row.medication_a_id, Medication.tenant_id == g.tenant_id)).scalars().first()
                    b = db.session.execute(select(Medication).filter(Medication.id == row.medication_b_id, Medication.tenant_id == g.tenant_id)).scalars().first()
                    a_name = a.trade_name if a else f"ID {row.medication_a_id}"
                    b_name = b.trade_name if b else f"ID {row.medication_b_id}"
                    warnings.append({
                        "a_id": row.medication_a_id, "b_id": row.medication_b_id,
                        "a_name": a_name, "b_name": b_name,
                        "severity": getattr(row, "severity", "unknown"),
                        "description": row.description or getattr(row, "interaction_type", f"تفاعل بين {a_name} و {b_name}"),
                    })
        except Exception as e:
            pass
        return warnings

    @staticmethod
    def check_patient_allergies(patient_id: int, medication_ids: list[int]) -> list[dict]:
        """Check if any medications conflict with patient allergies."""
        from models.patient import Patient, PatientAllergy
        from models.medication import Medication
        conflicts = []
        try:
            allergies = db.session.execute(select(PatientAllergy).filter_by(patient_id=patient_id)).scalars().all()
            if not allergies:
                return conflicts
            meds = db.session.execute(select(Medication).filter(Medication.id.in_(medication_ids))).scalars().all()
            for med in meds:
                for allergy in allergies:
                    allergen = allergy.allergen
                    names = ' '.join(filter(None, [med.trade_name, med.scientific_name]))
                    if allergen and names and allergen.lower() in names.lower():
                        conflicts.append({
                            "medication_id": med.id,
                            "medication_name": med.trade_name,
                            "allergen": allergen,
                            "severity": getattr(allergy, "severity", "warning"),
                        })
        except Exception as e:
            pass
        return conflicts

    # ==================== PRESCRIPTION CREATION ====================

    @staticmethod
    @require_module('pharmacy')
    def create_prescription(
        patient_id: int, doctor_id: int, visit_id: int | None = None,
        tenant_id: int | None = None,
        items: list[dict] | None = None, notes: str | None = None,
        diagnosis: str | None = None,
        prescription_number: str | None = None,
        skip_safety_checks: bool = False,
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

        resolved_tenant_id = tenant_id if tenant_id is not None else getattr(g, "tenant_id", None)

        if not skip_safety_checks and items:
            from services.clinical_safety_service import ClinicalSafetyService
            med_ids = [it.get("medication_id") for it in items if it.get("medication_id")]
            if med_ids and resolved_tenant_id:
                proposed = [{"drug_id": it.get("medication_id"), "dosage": it.get("dosage", ""), "quantity": it.get("quantity", 1), "duration_days": it.get("duration_days", 7)} for it in items if it.get("medication_id")]
                is_safe, safety_alerts = ClinicalSafetyService.check_prescription_safety(
                    patient_id=patient_id,
                    medication_id=med_ids[0],
                    proposed_items=proposed,
                    doctor_id=doctor_id,
                    tenant_id=resolved_tenant_id,
                )
                if not is_safe:
                    hard_stops = [a for a in safety_alerts if a.severity.value == 'hard_stop']
                    if hard_stops:
                        msgs = "; ".join(a.message for a in hard_stops)
                        return False, msgs

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
                    med = db.session.execute(select(Medication).filter(Medication.id == med_id, Medication.tenant_id == resolved_tenant_id)).scalars().first()
                    if not med:
                        safe_commit(db.session, error_message="Medication not found, rolling back")
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
            if not safe_commit(db.session, error_message="Failed to create prescription"):
                return False, "database_error"
            return True, prescription
        except Exception as e:
            logging.error(f"Error creating prescription: {str(e)}")
            return False, str(e)

    @staticmethod
    @require_module('pharmacy')
    def get_active_prescriptions(patient_id: int) -> list:
        from models.medication import Prescription
        return db.session.execute(select(Prescription).filter_by(
            patient_id=patient_id, status="active"
        ).order_by(Prescription.created_at.desc())).scalars().all()

    @staticmethod
    @require_module('pharmacy')
    def get_prescriptions_by_doctor(doctor_id: int, limit: int = 50) -> list:
        from models.medication import Prescription
        return db.session.execute(select(Prescription).filter_by(doctor_id=doctor_id).order_by(
            Prescription.created_at.desc()
        ).limit(limit)).scalars().all()

    # ==================== MEDICATION INVENTORY ====================

    @staticmethod
    @require_module('pharmacy')
    def get_low_stock_medications(limit: int = 10) -> list:
        from models.medication import Medication
        return db.session.execute(select(Medication).filter(
            Medication.stock_quantity <= Medication.minimum_stock
        ).limit(limit)).scalars().all()

    @staticmethod
    @require_module('pharmacy')
    def search_medications(query: str) -> list:
        from models.medication import Medication
        return db.session.execute(select(Medication).filter(
            or_(
                Medication.trade_name.ilike(f"%{query}%"),
                Medication.generic_name.ilike(f"%{query}%"),
            )
        ).order_by(Medication.trade_name)).scalars().all()

    @staticmethod
    @require_module('pharmacy')
    def update_stock(medication_id: int, quantity_change: float) -> bool:
        from models.medication import Medication
        try:
            med = db.session.execute(select(Medication).filter(Medication.id == medication_id, Medication.tenant_id == g.tenant_id)).scalars().first()
            if not med:
                return False
            med.stock_quantity = (med.stock_quantity or 0) + quantity_change
            return safe_commit(db.session, error_message="Failed to update stock")
        except Exception as e:
            logging.error(f"Error updating medication stock: {str(e)}")
            return False

    # ==================== SUPPLY REQUESTS ====================

    @staticmethod
    @require_module('pharmacy')
    def create_supply_request(
        medication_id: int, quantity: float, requested_by: int,
        notes: str | None = None
    ) -> Any | None:
        from models.medication import Medication
        from models.supply_request import MedicationSupplyRequest, MedicationSupplyRequestItem
        try:
            med = db.session.execute(select(Medication).filter(Medication.id == medication_id, Medication.tenant_id == g.tenant_id)).scalars().first()
            if not med:
                return None
            request = MedicationSupplyRequest(
                request_number=f"SR-{uuid.uuid4().hex[:8].upper()}",
                status="DRAFT",
                notes=notes,
                created_by=requested_by,
                created_at=datetime.now(timezone.utc),
            )
            db.session.add(request)
            db.session.flush()

            item = MedicationSupplyRequestItem(
                request_id=request.id,
                medication_id=medication_id,
                requested_qty=quantity,
            )
            db.session.add(item)
            if not safe_commit(db.session, error_message="Failed to create supply request"):
                return None
            return request
        except Exception as e:
            logging.error(f"Error creating supply request: {str(e)}")
            return None

    @staticmethod
    @require_module('pharmacy')
    def get_supply_requests(status: str | None = None) -> list:
        from models.supply_request import MedicationSupplyRequest
        q = MedicationSupplyRequest.query
        if status:
            q = q.filter_by(status=status)
        return q.order_by(MedicationSupplyRequest.created_at.desc()).all()

    # ==================== NOTIFICATION ====================

    @staticmethod
    @require_module('pharmacy')
    def notify_pharmacy_non_catalog(medication_name: str, doctor_name: str, visit_id: int) -> None:
        try:
            from services.notification_service import NotificationService
            NotificationService.send_notification(
                recipient_role="pharmacist",
                title="دواء خارج التصنيف",
                message=f"الطبيب {doctor_name} وصف دواء {medication_name} (خارج التصنيف) للزيارة #{visit_id}",
                notification_type="warning",
            )
        except Exception as e:
            pass

    # ==================== AUDIT ====================

    @staticmethod
    @require_module('pharmacy')
    def get_medication(medication_id: int):
        from models.medication import Medication
        return db.session.execute(select(Medication).filter(Medication.id == medication_id, Medication.tenant_id == g.tenant_id)).scalars().first()

    @staticmethod
    @require_module('pharmacy')
    def get_prescription(prescription_id: int):
        from models.medication import Prescription
        return db.session.execute(select(Prescription).filter(Prescription.id == prescription_id, Prescription.tenant_id == g.tenant_id)).scalars().first()

    @staticmethod
    @require_module('pharmacy')
    def log_action(action: str, details: str, user_id: int | None = None) -> None:
        from models.audit_trail import AuditTrail
        _allowed = {"create", "update", "delete", "view", "export", "import", "security"}
        try:
            log = AuditTrail(
                entity_type="system", entity_id=0,
                action=action if action in _allowed else "update",
                description=f"[medication] {action}: {details}" if details else f"[medication] {action}",
                user_id=user_id, created_at=datetime.now(timezone.utc),
            )
            db.session.add(log)
            safe_commit(db.session, error_message="Failed to log action")
        except Exception as e:
            pass


# Singleton
prescription_service = PrescriptionService()
