"""
HL7 FHIR API Routes — Basic REST API for interoperability
"""

from flask import Blueprint, abort, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from models.fhir_mapping import (
    FHIRAuditLog,
)
from models.lab_request import LabResult
from models.patient import Patient
from models.visit import Visit
from utils.db_safety import safe_commit, safe_rollback
from utils.decorators import handle_route_errors, role_required
from utils.tenant_query import get_tenant_record, tenant_filter

fhir_bp = Blueprint('fhir', __name__)


def _log_fhir_access(
    action, resource_type, resource_id=None, request_body=None, response_status=200
):
    import logging

    try:
        log = FHIRAuditLog(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=current_user.id if current_user.is_authenticated else None,
            ip_address=request.remote_addr,
            request_body=request_body[:1000] if request_body else None,
            response_status=response_status,
        )
        db.session.add(log)
        safe_commit(db.session, error_message='database commit failed', reraise=True)
    except Exception:
        safe_rollback(db.session, error_message='database rollback')
        logging.exception('FHIR audit log error: %s')


@fhir_bp.route('/Patient', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor')
@handle_route_errors
def fhir_patients():
    patients = (
        db.session.execute(tenant_filter(Patient).filter_by(status='ACTIVE').limit(100))
        .scalars()
        .all()
    )
    _log_fhir_access('SEARCH', 'Patient')
    return jsonify(
        {
            'resourceType': 'Bundle',
            'type': 'searchset',
            'total': len(patients),
            'entry': [
                {
                    'resource': {
                        'resourceType': 'Patient',
                        'id': str(p.id),
                        'name': [{'text': p.full_name}],
                        'gender': p.gender.lower() if p.gender else 'unknown',
                        'birthDate': p.birth_date.isoformat() if p.birth_date else None,
                    }
                }
                for p in patients
            ],
        }
    )


@fhir_bp.route('/Patient/<int:patient_id>', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor')
@handle_route_errors
def fhir_patient(patient_id):
    patient = get_tenant_record(Patient, patient_id)
    if not patient:
        abort(404)
    _log_fhir_access('READ', 'Patient', str(patient_id))
    return jsonify(
        {
            'resourceType': 'Patient',
            'id': str(patient.id),
            'identifier': [{'value': patient.national_id}] if patient.national_id else [],
            'name': [{'text': patient.full_name}],
            'telecom': [{'value': patient.phone, 'system': 'phone'}] if patient.phone else [],
            'gender': patient.gender.lower() if patient.gender else 'unknown',
            'birthDate': patient.birth_date.isoformat() if patient.birth_date else None,
            'address': [{'text': patient.address}] if patient.address else [],
        }
    )


@fhir_bp.route('/Encounter', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor')
@handle_route_errors
def fhir_encounters():
    visits = (
        db.session.execute(tenant_filter(Visit).order_by(Visit.created_at.desc()).limit(100))
        .scalars()
        .all()
    )
    _log_fhir_access('SEARCH', 'Encounter')
    return jsonify(
        {
            'resourceType': 'Bundle',
            'type': 'searchset',
            'total': len(visits),
            'entry': [
                {
                    'resource': {
                        'resourceType': 'Encounter',
                        'id': str(v.id),
                        'status': v.status.lower() if v.status else 'unknown',
                        'class': {'code': v.visit_type.lower() if v.visit_type else 'amb'},
                        'subject': {'reference': f'Patient/{v.patient_id}'},
                        'period': {'start': v.created_at.isoformat() if v.created_at else None},
                    }
                }
                for v in visits
            ],
        }
    )


@fhir_bp.route('/Observation', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor')
@handle_route_errors
def fhir_observations():
    patient_id = request.args.get('patient', type=int)
    results = []
    if patient_id:
        patient = get_tenant_record(Patient, patient_id)
        if not patient:
            abort(404)
        lab_results = (
            db.session.execute(select(LabResult).filter_by(patient_id=patient_id).limit(50))
            .scalars()
            .all()
        )
        for lr in lab_results:
            results.append(
                {
                    'resourceType': 'Observation',
                    'id': f'lab-{lr.id}',
                    'status': 'final',
                    'category': [
                        {
                            'coding': [
                                {
                                    'system': 'http://terminology.hl7.org/CodeSystem/observation-category',
                                    'code': 'laboratory',
                                }
                            ]
                        }
                    ],
                    'code': {'text': lr.test_name},
                    'subject': {'reference': f'Patient/{lr.patient_id}'},
                    'valueString': lr.result_value,
                }
            )
    _log_fhir_access('SEARCH', 'Observation')
    return jsonify(
        {
            'resourceType': 'Bundle',
            'type': 'searchset',
            'total': len(results),
            'entry': [{'resource': r} for r in results],
        }
    )
