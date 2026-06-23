"""
Clinical Context Service - provides unified clinical context for a visit
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone


class ClinicalContextService:
    """Provides aggregated clinical data for a visit context."""

    @staticmethod
    def get_visit_context(visit_id: int) -> Dict[str, Any]:
        """Build complete clinical context for a visit (vitals, allergies, diagnoses, orders, results)."""
        from models.visit import Visit
        from models.nurse import VitalSigns
        from models.lab_request import LabRequest, LabResult
        from models.radiology_request import RadiologyRequest
        from models.radiology_result import RadiologyResult
        from models.medication import Prescription, PrescriptionItem
        from models.patient import Patient, PatientAllergy
        from models.workflow import VisitWorkflowEvent

        visit = Visit.query.get(visit_id)
        if not visit:
            return {}

        patient = Patient.query.get(visit.patient_id)
        vitals = VitalSigns.query.filter_by(visit_id=visit_id).order_by(VitalSigns.recorded_at.desc()).all()
        allergies = PatientAllergy.query.filter_by(patient_id=visit.patient_id).all()
        lab_reqs = LabRequest.query.filter_by(visit_id=visit_id).all()
        rad_reqs = RadiologyRequest.query.filter_by(visit_id=visit_id).all()
        prescriptions = Prescription.query.filter_by(visit_id=visit_id).all()
        from models.icd_coding import CodedDiagnosis
        diagnoses = CodedDiagnosis.query.filter_by(visit_id=visit_id).all()

        return {
            "visit": visit.to_dict() if hasattr(visit, 'to_dict') else {"id": visit.id, "status": visit.status},
            "patient": patient.to_dict() if hasattr(patient, 'to_dict') else {"id": patient.id, "name": patient.full_name},
            "vitals": [{"bp": f"{v.blood_pressure_systolic}/{v.blood_pressure_diastolic}", "hr": v.heart_rate, "temp": v.temperature,
                        "rr": v.respiratory_rate, "spo2": v.oxygen_saturation, "recorded_at": str(v.recorded_at)} for v in vitals],
            "allergies": [{"medication": a.allergen, "severity": a.severity} for a in allergies],
            "diagnoses": [
                {
                    "code": d.icd_code.code if d.icd_code else "",
                    "name": d.icd_code.description if d.icd_code else "",
                    "type": d.diagnosis_type,
                }
                for d in diagnoses
            ],
            "lab_requests": [{"id": r.id, "test": r.test_name, "status": r.status} for r in lab_reqs],
            "radiology_requests": [{"id": r.id, "test": r.test_name, "status": r.status} for r in rad_reqs],
            "prescriptions": [{"id": p.id, "status": p.status} for p in prescriptions],
        }

    @staticmethod
    def get_timeline(visit_id: int) -> List[Dict[str, Any]]:
        """Build chronological timeline of events for a visit."""
        from models.workflow import VisitWorkflowEvent
        events = VisitWorkflowEvent.query.filter_by(visit_id=visit_id).order_by(VisitWorkflowEvent.created_at).all()
        return [
            {
                "timestamp": str(e.created_at),
                "actor": f"User #{e.performed_by}" if e.performed_by else "System",
                "action": f"{e.from_status} -> {e.to_status}",
                "detail": e.notes or "",
            }
            for e in events
        ]
