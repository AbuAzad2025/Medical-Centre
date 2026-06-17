"""
HL7 FHIR API Routes — Basic REST API for interoperability
"""
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from utils.decorators import handle_route_errors, role_required
from models.fhir_mapping import FHIRPatient, FHIRObservation, FHIREncounter, FHIRDocumentReference, FHIRAuditLog
from models.patient import Patient
from models.visit import Visit
from models.lab_request import LabRequest, LabResult
from models.radiology_request import RadiologyRequest
from models.radiology_test import RadiologyResult
from services.fhir_service import fhir_service
from app_factory import db
import json, uuid
from datetime import datetime, timezone

fhir_bp = Blueprint('fhir', __name__)

def _log_fhir_access(action, resource_type, resource_id=None, request_body=None, response_status=200):
    log = FHIRAuditLog(
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        user_id=current_user.id if current_user.is_authenticated else None,
        ip_address=request.remote_addr,
        request_body=request_body[:1000] if request_body else None,
        response_status=response_status
    )
    db.session.add(log)
    db.session.commit()

@fhir_bp.route('/Patient', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor')
@handle_route_errors
def fhir_patients():
    patients = Patient.query.filter_by(status='ACTIVE').limit(100).all()
    _log_fhir_access('SEARCH', 'Patient')
    return jsonify({
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(patients),
        "entry": [{"resource": {
            "resourceType": "Patient",
            "id": str(p.id),
            "name": [{"text": p.full_name}],
            "gender": p.gender.lower() if p.gender else 'unknown',
            "birthDate": p.birth_date.isoformat() if p.birth_date else None
        }} for p in patients]
    })

@fhir_bp.route('/Patient/<int:patient_id>', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor')
@handle_route_errors
def fhir_patient(patient_id):
    patient = Patient.query.get_or_404(patient_id)
    _log_fhir_access('READ', 'Patient', str(patient_id))
    return jsonify({
        "resourceType": "Patient",
        "id": str(patient.id),
        "identifier": [{"value": patient.national_id}] if patient.national_id else [],
        "name": [{"text": patient.full_name}],
        "telecom": [{"value": patient.phone, "system": "phone"}] if patient.phone else [],
        "gender": patient.gender.lower() if patient.gender else 'unknown',
        "birthDate": patient.birth_date.isoformat() if patient.birth_date else None,
        "address": [{"text": patient.address}] if patient.address else []
    })

@fhir_bp.route('/Encounter', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor')
@handle_route_errors
def fhir_encounters():
    visits = Visit.query.order_by(Visit.created_at.desc()).limit(100).all()
    _log_fhir_access('SEARCH', 'Encounter')
    return jsonify({
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(visits),
        "entry": [{"resource": {
            "resourceType": "Encounter",
            "id": str(v.id),
            "status": v.status.lower() if v.status else 'unknown',
            "class": {"code": v.visit_type.lower() if v.visit_type else 'amb'},
            "subject": {"reference": f"Patient/{v.patient_id}"},
            "period": {"start": v.created_at.isoformat() if v.created_at else None}
        }} for v in visits]
    })

@fhir_bp.route('/Observation', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor')
@handle_route_errors
def fhir_observations():
    patient_id = request.args.get('patient', type=int)
    results = []
    if patient_id:
        lab_results = LabResult.query.filter_by(patient_id=patient_id).limit(50).all()
        for lr in lab_results:
            results.append({
                "resourceType": "Observation",
                "id": f"lab-{lr.id}",
                "status": "final",
                "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "laboratory"}]}],
                "code": {"text": lr.test_name},
                "subject": {"reference": f"Patient/{lr.patient_id}"},
                "valueString": lr.result_value
            })
    _log_fhir_access('SEARCH', 'Observation')
    return jsonify({
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(results),
        "entry": [{"resource": r} for r in results]
    })
