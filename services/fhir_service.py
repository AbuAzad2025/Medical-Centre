"""
FHIR Service - HL7 FHIR resource serialization and audit logging.
Extracted from routes/fhir_api_routes.py.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from app_factory import db
from flask import request


class FHIRService:
    """Centralized FHIR interoperability business logic"""

    # ==================== AUDIT LOGGING ====================

    @staticmethod
    def log_access(action: str, resource_type: str, resource_id: str | None = None,
                   request_body: str | None = None, response_status: int = 200,
                   user_id: int | None = None) -> None:
        from models.fhir_mapping import FHIRAuditLog
        try:
            log = FHIRAuditLog(
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                user_id=user_id,
                ip_address=request.remote_addr,
                request_body=request_body[:1000] if request_body else None,
                response_status=response_status,
            )
            db.session.add(log)
            db.session.commit()
        except Exception:
            db.session.rollback()

    # ==================== PATIENT RESOURCES ====================

    @staticmethod
    def serialize_patient(patient: Any) -> dict:
        return {
            "resourceType": "Patient",
            "id": str(patient.id),
            "identifier": [{"value": patient.national_id}] if patient.national_id else [],
            "name": [{"text": patient.full_name}],
            "telecom": [{"value": patient.phone, "system": "phone"}] if patient.phone else [],
            "gender": patient.gender.lower() if patient.gender else "unknown",
            "birthDate": patient.birth_date.isoformat() if patient.birth_date else None,
            "address": [{"text": patient.address}] if patient.address else [],
        }

    @staticmethod
    def serialize_patient_bundle(patients: list) -> dict:
        return {
            "resourceType": "Bundle",
            "type": "searchset",
            "total": len(patients),
            "entry": [{"resource": FHIRService.serialize_patient(p)} for p in patients],
        }

    @staticmethod
    def get_all_patients(limit: int = 100) -> list:
        from models.patient import Patient
        return Patient.query.filter_by(status="ACTIVE").limit(limit).all()

    @staticmethod
    def get_patient(patient_id: int) -> Any | None:
        from models.patient import Patient
        return Patient.query.get(patient_id)

    # ==================== ENCOUNTER RESOURCES ====================

    @staticmethod
    def serialize_encounter(visit: Any) -> dict:
        return {
            "resourceType": "Encounter",
            "id": str(visit.id),
            "status": "finished" if visit.status in ("COMPLETED", "DISCHARGED") else "in-progress",
            "class": {"code": visit.visit_type or "OUTPATIENT"},
            "subject": {"reference": f"Patient/{visit.patient_id}"},
            "period": {
                "start": visit.created_at.isoformat() if visit.created_at else None,
                "end": visit.updated_at.isoformat() if visit.updated_at else None,
            },
        }

    @staticmethod
    def serialize_encounter_bundle(visits: list) -> dict:
        return {
            "resourceType": "Bundle",
            "type": "searchset",
            "total": len(visits),
            "entry": [{"resource": FHIRService.serialize_encounter(v)} for v in visits],
        }

    @staticmethod
    def get_all_encounters(limit: int = 100) -> list:
        from models.visit import Visit
        return Visit.query.order_by(Visit.created_at.desc()).limit(limit).all()

    # ==================== OBSERVATION RESOURCES ====================

    @staticmethod
    def serialize_lab_observation(result: Any) -> dict:
        return {
            "resourceType": "Observation",
            "id": str(result.id),
            "status": "final" if getattr(result, 'result_status', '') == 'COMPLETED' else "preliminary",
            "code": {"text": result.test_name or getattr(result, 'test_type', 'Lab Test')},
            "subject": {"reference": f"Patient/{result.patient_id}"},
            "encounter": {"reference": f"Encounter/{result.visit_id}"} if getattr(result, 'visit_id', None) else None,
            "valueQuantity": {
                "value": result.result_value,
                "unit": result.unit or "",
            } if getattr(result, 'result_value', None) else None,
            "interpretation": [{"text": result.interpretation}] if getattr(result, 'interpretation', None) else [],
        }

    @staticmethod
    def serialize_radiology_observation(result: Any) -> dict:
        return {
            "resourceType": "Observation",
            "id": str(result.id),
            "status": "final" if getattr(result, 'status', '') == 'COMPLETED' else "preliminary",
            "code": {"text": result.test_name or getattr(result, 'procedure_name', 'Radiology Test')},
            "subject": {"reference": f"Patient/{result.patient_id}"},
            "valueString": result.impressions or result.findings or "",
        }

    # ==================== DOCUMENT REFERENCE ====================

    @staticmethod
    def serialize_document(document: Any) -> dict:
        return {
            "resourceType": "DocumentReference",
            "id": str(document.id),
            "status": "current",
            "type": {"text": getattr(document, 'document_type', 'General')},
            "subject": {"reference": f"Patient/{document.patient_id}"},
            "content": [{"attachment": {"url": getattr(document, 'file_url', '')}}],
            "context": {"period": {
                "start": document.created_at.isoformat() if document.created_at else None,
            }} if getattr(document, 'created_at', None) else {},
        }


# Singleton
fhir_service = FHIRService()
