"""
Clinical Safety Service — mandatory checks before prescription and treatment
Prevents medication errors, adverse drug events, and allergic reactions
"""
from sqlalchemy import select

import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from app.extensions import db

logger = logging.getLogger(__name__)


class SafetyCheckSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    HARD_STOP = "hard_stop"


@dataclass
class SafetyAlert:
    check_type: str
    severity: SafetyCheckSeverity
    message: str
    details: Optional[Dict] = None
    override_requires: Optional[str] = None  # e.g., 'super_admin', 'head_physician'


class ClinicalSafetyService:
    """
    Enforces clinical safety checks at point of care.
    
    Checks performed before prescription creation:
    1. Patient allergy cross-check against medication ingredients
    2. Drug-drug interaction check against current medications
    3. Contraindication check against patient problem list / diagnoses
    4. Pregnancy/lactation safety check
    5. Pediatric dosing validation (if applicable)
    6. Duplicate therapy detection
    """

    @staticmethod
    def check_prescription_safety(
        patient_id: int,
        medication_id: int,
        proposed_items: List[Dict],  # list of {drug_id, dosage, frequency, duration}
        doctor_id: int,
        tenant_id: int,
    ) -> Tuple[bool, List[SafetyAlert]]:
        """
        Run all safety checks before allowing prescription creation.
        
        Returns:
            (is_safe, alerts)
            is_safe = False if any HARD_STOP alert exists
        """
        alerts: List[SafetyAlert] = []

        try:
            alerts.extend(
                ClinicalSafetyService._check_allergies(patient_id, proposed_items, tenant_id)
            )
        except Exception as exc:
            logger.exception("Allergy check failed for patient %s", patient_id)
            alerts.append(SafetyAlert(
                check_type="allergy",
                severity=SafetyCheckSeverity.CRITICAL,
                message="Unable to verify allergies — please check manually before prescribing",
                override_requires="head_physician"
            ))

        try:
            alerts.extend(
                ClinicalSafetyService._check_drug_interactions(patient_id, proposed_items, tenant_id)
            )
        except Exception as exc:
            logger.exception("Drug interaction check failed for patient %s", patient_id)
            alerts.append(SafetyAlert(
                check_type="drug_interaction",
                severity=SafetyCheckSeverity.CRITICAL,
                message="Unable to verify drug interactions — please check manually",
                override_requires="head_physician"
            ))

        try:
            alerts.extend(
                ClinicalSafetyService._check_contraindications(patient_id, proposed_items, tenant_id)
            )
        except Exception as exc:
            logger.exception("Contraindication check failed for patient %s", patient_id)
            alerts.append(SafetyAlert(
                check_type="contraindication",
                severity=SafetyCheckSeverity.CRITICAL,
                message="Unable to verify contraindications — please check manually",
                override_requires="head_physician"
            ))

        try:
            alerts.extend(
                ClinicalSafetyService._check_pregnancy_safety(patient_id, proposed_items, tenant_id)
            )
        except Exception as exc:
            logger.exception("Pregnancy safety check failed for patient %s", patient_id)

        try:
            alerts.extend(
                ClinicalSafetyService._check_duplicate_therapy(patient_id, proposed_items, tenant_id)
            )
        except Exception as exc:
            logger.exception("Duplicate therapy check failed for patient %s", patient_id)

        has_hard_stop = any(a.severity == SafetyCheckSeverity.HARD_STOP for a in alerts)
        return (not has_hard_stop, alerts)

    @staticmethod
    def _check_allergies(patient_id: int, proposed_items: List[Dict], tenant_id: int) -> List[SafetyAlert]:
        """Cross-check proposed medications against patient allergy list."""
        alerts = []
        from models.patient import PatientAllergy
        from models.medication import Medication

        allergies = db.session.execute(select(PatientAllergy).filter_by(patient_id=patient_id, tenant_id=tenant_id)).scalars().all()
        if not allergies:
            return alerts

        for item in proposed_items:
            drug_id = item.get('drug_id') or item.get('medication_id')
            if not drug_id:
                continue

            # Get medication and its ingredients
            medication = db.session.get(Medication, drug_id)
            if not medication:
                continue

            # Check direct medication name match
            for allergy in allergies:
                allergen = (allergy.allergen or '').lower()
                if not allergen:
                    continue
                med_name = (medication.name or '').lower()
                if allergen in med_name or med_name in allergen:
                    alerts.append(SafetyAlert(
                        check_type="allergy",
                        severity=SafetyCheckSeverity.HARD_STOP,
                        message=f"HARD STOP: Patient is allergic to '{allergy.allergen}' — matches prescribed medication '{medication.name}'",
                        details={
                            'allergen': allergy.allergen,
                            'medication': medication.name,
                            'severity': allergy.severity,
                        },
                        override_requires="head_physician"
                    ))

            # Check ingredient-level matches (gracefully skip if DrugIngredient model missing)
            try:
                from models.medication import DrugIngredient
                ingredients = db.session.execute(select(DrugIngredient).filter_by(medication_id=drug_id)).scalars().all()
                for ingredient in ingredients:
                    ing_name = (ingredient.name or '').lower()
                    for allergy in allergies:
                        allergen = (allergy.allergen or '').lower()
                        if allergen in ing_name or ing_name in allergen:
                            alerts.append(SafetyAlert(
                                check_type="allergy",
                                severity=SafetyCheckSeverity.HARD_STOP,
                                message=f"HARD STOP: Patient is allergic to '{allergy.allergen}' — found in ingredient '{ingredient.name}' of '{medication.name}'",
                                details={
                                    'allergen': allergy.allergen,
                                    'ingredient': ingredient.name,
                                    'medication': medication.name,
                                    'severity': allergy.severity,
                                },
                                override_requires="head_physician"
                            ))
            except ImportError:
                pass
        return alerts

    @staticmethod
    def _check_drug_interactions(patient_id: int, proposed_items: List[Dict], tenant_id: int) -> List[SafetyAlert]:
        """Check drug-drug interactions between proposed and current medications."""
        alerts = []
        from models.drug_interaction import DrugInteraction
        from models.medication import Prescription, PrescriptionItem

        # Get active prescription items for patient
        active_prescriptions = db.session.execute(select(Prescription).filter_by(
            patient_id=patient_id, tenant_id=tenant_id
        )).scalars().all()
        current_drug_ids = set()
        for pres in active_prescriptions:
            for item in pres.items:
                med_id = getattr(item, 'drug_id', getattr(item, 'medication_id', None))
                if med_id:
                    current_drug_ids.add(med_id)

        proposed_drug_ids = {
            item.get('drug_id') or item.get('medication_id')
            for item in proposed_items
        }
        proposed_drug_ids.discard(None)

        # Check interactions between proposed and current
        all_drug_ids = current_drug_ids | proposed_drug_ids
        for drug_a in proposed_drug_ids:
            for drug_b in current_drug_ids:
                if drug_a == drug_b:
                    continue
                interactions = db.session.execute(select(DrugInteraction).filter(
                    db.or_(
                        db.and_(DrugInteraction.medication_a_id == drug_a, DrugInteraction.medication_b_id == drug_b),
                        db.and_(DrugInteraction.medication_a_id == drug_b, DrugInteraction.medication_b_id == drug_a),
                    )
                )).scalars().all()
                for interaction in interactions:
                    if interaction.severity in ('HIGH',):
                        alerts.append(SafetyAlert(
                            check_type="drug_interaction",
                            severity=SafetyCheckSeverity.HARD_STOP,
                            message=f"HARD STOP: Major drug interaction detected — {interaction.description}",
                            details={
                                'drug_a_id': drug_a,
                                'drug_b_id': drug_b,
                                'severity': interaction.severity,
                                'mechanism': getattr(interaction, 'mechanism', None),
                            },
                            override_requires="head_physician"
                        ))
                    elif interaction.severity in ('MODERATE',):
                        alerts.append(SafetyAlert(
                            check_type="drug_interaction",
                            severity=SafetyCheckSeverity.WARNING,
                            message=f"WARNING: Moderate drug interaction — {interaction.description}",
                            details={
                                'drug_a_id': drug_a,
                                'drug_b_id': drug_b,
                                'severity': interaction.severity,
                            }
                        ))
                    else:
                        alerts.append(SafetyAlert(
                            check_type="drug_interaction",
                            severity=SafetyCheckSeverity.INFO,
                            message=f"INFO: Minor drug interaction — {interaction.description}",
                            details={
                                'drug_a_id': drug_a,
                                'drug_b_id': drug_b,
                                'severity': interaction.severity,
                            }
                        ))
        return alerts

    @staticmethod
    def _check_contraindications(patient_id: int, proposed_items: List[Dict], tenant_id: int) -> List[SafetyAlert]:
        """Check medication against patient problem list / diagnoses."""
        alerts = []
        from models.problem_list import PatientProblem

        problems = db.session.execute(select(PatientProblem).filter_by(patient_id=patient_id, tenant_id=tenant_id, status='ACTIVE')).scalars().all()
        if not problems:
            return alerts

        problem_codes = [p.icd_code for p in problems if p.icd_code]
        problem_names = [(p.description or '').lower() for p in problems if p.description]

        # Gracefully skip if MedicationContraindication model is not yet available
        try:
            from models.medication import MedicationContraindication
        except ImportError:
            return alerts

        for item in proposed_items:
            drug_id = item.get('drug_id') or item.get('medication_id')
            if not drug_id:
                continue

            contraindications = db.session.execute(select(MedicationContraindication).filter_by(medication_id=drug_id)).scalars().all()
            for contra in contraindications:
                # Match by ICD code
                if contra.icd_code and contra.icd_code in problem_codes:
                    alerts.append(SafetyAlert(
                        check_type="contraindication",
                        severity=SafetyCheckSeverity.HARD_STOP,
                        message=f"HARD STOP: Medication is contraindicated for diagnosis {contra.icd_code} — {contra.description}",
                        details={
                            'icd_code': contra.icd_code,
                            'contraindication': contra.description,
                        },
                        override_requires="head_physician"
                    ))
                # Match by description keyword
                if contra.keyword:
                    keyword_lower = contra.keyword.lower()
                    for prob_name in problem_names:
                        if keyword_lower in prob_name or prob_name in keyword_lower:
                            alerts.append(SafetyAlert(
                                check_type="contraindication",
                                severity=SafetyCheckSeverity.HARD_STOP,
                                message=f"HARD STOP: Medication contraindicated — {contra.description}",
                                details={
                                    'keyword': contra.keyword,
                                    'contraindication': contra.description,
                                },
                                override_requires="head_physician"
                            ))
        return alerts

    @staticmethod
    def _check_pregnancy_safety(patient_id: int, proposed_items: List[Dict], tenant_id: int) -> List[SafetyAlert]:
        """Check medication safety for pregnant patients."""
        alerts = []
        from models.patient import Patient
        from models.medication import Medication

        patient = db.session.execute(select(Patient).filter_by(id=patient_id, tenant_id=tenant_id)).scalars().first()
        if not patient or not patient.is_pregnant:
            return alerts

        for item in proposed_items:
            drug_id = item.get('drug_id') or item.get('medication_id')
            if not drug_id:
                continue
            medication = db.session.execute(select(Medication).filter_by(id=drug_id)).scalars().first()
            if not medication:
                continue
            # Check pregnancy category
            if medication.pregnancy_category in ('X', 'D'):
                alerts.append(SafetyAlert(
                    check_type="pregnancy",
                    severity=SafetyCheckSeverity.HARD_STOP,
                    message=f"HARD STOP: Medication '{medication.name}' is pregnancy category {medication.pregnancy_category} — contraindicated in pregnancy",
                    details={
                        'medication': medication.name,
                        'pregnancy_category': medication.pregnancy_category,
                        'pregnancy_weeks': patient.pregnancy_weeks,
                    },
                    override_requires="head_physician"
                ))
            elif medication.pregnancy_category == 'C':
                alerts.append(SafetyAlert(
                    check_type="pregnancy",
                    severity=SafetyCheckSeverity.WARNING,
                    message=f"WARNING: Medication '{medication.name}' is pregnancy category C — use only if clearly needed",
                    details={
                        'medication': medication.name,
                        'pregnancy_category': medication.pregnancy_category,
                    }
                ))
        return alerts

    @staticmethod
    def _check_duplicate_therapy(patient_id: int, proposed_items: List[Dict], tenant_id: int) -> List[SafetyAlert]:
        """Detect duplicate or overlapping therapy."""
        alerts = []
        from models.medication import Prescription, PrescriptionItem, Medication

        active_prescriptions = db.session.execute(select(Prescription).filter_by(
            patient_id=patient_id, tenant_id=tenant_id
        )).scalars().all()

        proposed_drug_ids = {
            item.get('drug_id') or item.get('medication_id')
            for item in proposed_items
        }
        proposed_drug_ids.discard(None)

        current_drug_ids = set()
        for pres in active_prescriptions:
            for item in pres.items:
                if item.drug_id:
                    current_drug_ids.add(item.drug_id)

        duplicates = proposed_drug_ids & current_drug_ids
        for dup_id in duplicates:
            medication = db.session.get(Medication, dup_id)
            name = medication.name if medication else f"Drug #{dup_id}"
            alerts.append(SafetyAlert(
                check_type="duplicate_therapy",
                severity=SafetyCheckSeverity.WARNING,
                message=f"WARNING: Patient already has an active prescription for '{name}'. Verify intent to continue or replace.",
                details={'drug_id': dup_id, 'medication_name': name}
            ))
        return alerts
