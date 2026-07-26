"""
Clinical Context Service - provides unified clinical context for a visit
"""
from sqlalchemy import select
from app.extensions import db
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from utils.tenant_query import get_tenant_record, TenantContextError


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

        try:
            visit = get_tenant_record(Visit, visit_id)
        except TenantContextError:
            return {}

        patient = get_tenant_record(Patient, visit.patient_id)
        vitals = db.session.execute(select(VitalSigns).filter_by(visit_id=visit_id).order_by(VitalSigns.recorded_at.desc())).scalars().all()
        allergies = db.session.execute(select(PatientAllergy).filter_by(patient_id=visit.patient_id)).scalars().all()
        lab_reqs = db.session.execute(select(LabRequest).filter_by(visit_id=visit_id)).scalars().all()
        rad_reqs = db.session.execute(select(RadiologyRequest).filter_by(visit_id=visit_id)).scalars().all()
        prescriptions = db.session.execute(select(Prescription).filter_by(visit_id=visit_id)).scalars().all()
        from models.icd_coding import CodedDiagnosis
        diagnoses = db.session.execute(select(CodedDiagnosis).filter_by(visit_id=visit_id)).scalars().all()

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
        events = db.session.execute(select(VisitWorkflowEvent).filter_by(visit_id=visit_id).order_by(VisitWorkflowEvent.created_at)).scalars().all()
        return [
            {
                "timestamp": str(e.created_at),
                "actor": f"User #{e.performed_by}" if e.performed_by else "System",
                "action": f"{e.from_status} -> {e.to_status}",
                "detail": e.notes or "",
            }
            for e in events
        ]
