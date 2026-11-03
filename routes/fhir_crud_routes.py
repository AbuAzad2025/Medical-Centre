"""FHIR POST/PUT and validation utilities."""

from __future__ import annotations

import contextlib

from flask import Blueprint, abort, g, jsonify, request
from flask_login import login_required

from app.extensions import db
from utils.db_safety import safe_commit
from utils.decorators import handle_route_errors, role_required
from utils.tenant_query import get_tenant_record

fhir_crud_bp = Blueprint('fhir_crud', __name__)


def _log(action, rt, rid=None):
    try:
        from models.fhir_mapping import FHIRAuditLog
        from utils.db_safety import safe_commit, safe_rollback

        log = FHIRAuditLog(
            action=action, resource_type=rt, resource_id=rid, user_id=None, ip_address=None
        )
        db.session.add(log)
        safe_commit(db.session, error_message='commit', reraise=True)
    except Exception:
        safe_rollback(db.session, error_message='rollback')


def _validate_fhir_resource(data):
    """Validate FHIR resource and return OperationOutcome issues."""
    issues = []
    if not isinstance(data, dict):
        return [
            {
                'severity': 'error',
                'code': 'invalid',
                'details': {'text': 'Resource must be a JSON object'},
            }
        ]
    if 'resourceType' not in data:
        issues.append(
            {
                'severity': 'error',
                'code': 'required',
                'details': {'text': 'Missing required field: resourceType'},
            }
        )
        return issues
    rt = data['resourceType']
    # Resource-specific validation
    if rt == 'Patient':
        if 'name' not in data and 'identifier' not in data:
            issues.append(
                {
                    'severity': 'error',
                    'code': 'required',
                    'details': {'text': 'Patient requires name or identifier'},
                }
            )
    elif rt == 'Observation':
        if 'status' not in data:
            issues.append(
                {
                    'severity': 'error',
                    'code': 'required',
                    'details': {'text': 'Observation requires status'},
                }
            )
        if 'code' not in data:
            issues.append(
                {
                    'severity': 'error',
                    'code': 'required',
                    'details': {'text': 'Observation requires code'},
                }
            )
    elif rt == 'Condition':
        if 'subject' not in data:
            issues.append(
                {
                    'severity': 'error',
                    'code': 'required',
                    'details': {'text': 'Condition requires subject'},
                }
            )
    elif rt == 'MedicationRequest':
        if 'status' not in data:
            issues.append(
                {
                    'severity': 'error',
                    'code': 'required',
                    'details': {'text': 'MedicationRequest requires status'},
                }
            )
        if 'intent' not in data:
            issues.append(
                {
                    'severity': 'error',
                    'code': 'required',
                    'details': {'text': 'MedicationRequest requires intent'},
                }
            )
        if 'medicationCodeableConcept' not in data and 'medicationReference' not in data:
            issues.append(
                {
                    'severity': 'error',
                    'code': 'required',
                    'details': {'text': 'MedicationRequest requires medication'},
                }
            )
        if 'subject' not in data:
            issues.append(
                {
                    'severity': 'error',
                    'code': 'required',
                    'details': {'text': 'MedicationRequest requires subject'},
                }
            )
    return issues


# --- POST/PUT Patient ---
@fhir_crud_bp.route('/Patient', methods=['POST'])
@login_required
@role_required('admin', 'manager', 'doctor', 'reception')
@handle_route_errors
def create_patient():
    data = request.get_json() or {}
    issues = _validate_fhir_resource(data)
    if issues:
        return jsonify({'resourceType': 'OperationOutcome', 'issue': issues}), 400

    from models.patient import Patient

    name = data.get('name', [{}])[0].get('text', '') if data.get('name') else ''
    if not name and data.get('name'):
        given = data['name'][0].get('given', [])
        family = data['name'][0].get('family', '')
        name = ' '.join([*given, family]).strip()

    name_parts = name.split(' ', 1)
    patient = Patient(
        tenant_id=getattr(g, 'tenant_id', None),
        first_name=name_parts[0] if name_parts else 'Unknown',
        last_name=name_parts[1] if len(name_parts) > 1 else '',
        gender=data.get('gender', 'unknown'),
        phone=data.get('telecom', [{}])[0].get('value') if data.get('telecom') else None,
        address=data.get('address', [{}])[0].get('text') if data.get('address') else None,
    )
    if data.get('birthDate'):
        from datetime import date

        with contextlib.suppress(ValueError):
            patient.birth_date = date.fromisoformat(data['birthDate'])
    if data.get('identifier'):
        patient.national_id = data['identifier'][0].get('value')

    db.session.add(patient)
    safe_commit(db.session, error_message='commit', reraise=True)
    _log('CREATE', 'Patient', str(patient.id))
    return jsonify(
        {
            'resourceType': 'Patient',
            'id': str(patient.id),
            'name': [{'text': patient.full_name}],
            'gender': patient.gender,
            'birthDate': patient.birth_date.isoformat() if patient.birth_date else None,
        }
    ), 201


@fhir_crud_bp.route('/Patient/<int:pid>', methods=['PUT'])
@login_required
@role_required('admin', 'manager', 'doctor', 'reception')
@handle_route_errors
def update_patient(pid):
    data = request.get_json() or {}
    issues = _validate_fhir_resource(data)
    if issues:
        return jsonify({'resourceType': 'OperationOutcome', 'issue': issues}), 400

    from models.patient import Patient

    try:
        patient = get_tenant_record(Patient, pid)
    except Exception:
        abort(404)

    name = data.get('name', [{}])[0].get('text', '') if data.get('name') else ''
    if name:
        name_parts = name.split(' ', 1)
        patient.first_name = name_parts[0]
        patient.last_name = name_parts[1] if len(name_parts) > 1 else ''
    if data.get('gender'):
        patient.gender = data['gender']
    if data.get('telecom'):
        patient.phone = data['telecom'][0].get('value')
    if data.get('address'):
        patient.address = data['address'][0].get('text')
    if data.get('birthDate'):
        from datetime import date

        with contextlib.suppress(ValueError):
            patient.birth_date = date.fromisoformat(data['birthDate'])

    safe_commit(db.session, error_message='commit', reraise=True)
    _log('UPDATE', 'Patient', str(pid))
    return jsonify(
        {
            'resourceType': 'Patient',
            'id': str(patient.id),
            'name': [{'text': patient.full_name}],
            'gender': patient.gender,
        }
    )


# --- POST/PUT Observation ---
@fhir_crud_bp.route('/Observation', methods=['POST'])
@login_required
@role_required('admin', 'manager', 'doctor', 'nurse', 'lab')
@handle_route_errors
def create_observation():
    data = request.get_json() or {}
    issues = _validate_fhir_resource(data)
    if issues:
        return jsonify({'resourceType': 'OperationOutcome', 'issue': issues}), 400

    from models.nurse import VitalSigns as Vital

    vital = Vital(
        tenant_id=getattr(g, 'tenant_id', None),
        patient_id=int(data.get('subject', {}).get('reference', '').split('/')[-1])
        if data.get('subject')
        else None,
    )
    if data.get('effectiveDateTime'):
        from datetime import datetime

        with contextlib.suppress(ValueError):
            vital.recorded_at = datetime.fromisoformat(
                data['effectiveDateTime'].replace('Z', '+00:00')
            )
    # Extract value from component or valueQuantity
    if data.get('valueQuantity'):
        vq = data['valueQuantity']
        if 'value' in vq:
            vital.temperature = (
                vq['value'] if 'temperature' in str(data.get('code', {})).lower() else None
            )

    db.session.add(vital)
    safe_commit(db.session, error_message='commit', reraise=True)
    _log('CREATE', 'Observation', str(vital.id))
    return jsonify({'resourceType': 'Observation', 'id': str(vital.id), 'status': 'final'}), 201


# --- POST Condition ---
@fhir_crud_bp.route('/Condition', methods=['POST'])
@login_required
@role_required('admin', 'manager', 'doctor')
@handle_route_errors
def create_condition():
    data = request.get_json() or {}
    issues = _validate_fhir_resource(data)
    if issues:
        return jsonify({'resourceType': 'OperationOutcome', 'issue': issues}), 400

    from models.medical_record import MedicalRecord

    patient_id = (
        int(data.get('subject', {}).get('reference', '').split('/')[-1])
        if data.get('subject')
        else None
    )
    record = MedicalRecord(
        tenant_id=getattr(g, 'tenant_id', None),
        patient_id=patient_id,
        title=data.get('code', {}).get('text', 'Unknown') or 'Unknown',
        diagnosis=data.get('code', {}).get('text'),
    )
    db.session.add(record)
    safe_commit(db.session, error_message='commit', reraise=True)
    _log('CREATE', 'Condition', str(record.id))
    return jsonify(
        {
            'resourceType': 'Condition',
            'id': str(record.id),
            'code': {'text': record.diagnosis},
            'subject': {'reference': f'Patient/{patient_id}'},
        }
    ), 201


# --- POST MedicationRequest ---
@fhir_crud_bp.route('/MedicationRequest', methods=['POST'])
@login_required
@role_required('admin', 'manager', 'doctor')
@handle_route_errors
def create_medication_request():
    data = request.get_json() or {}
    issues = _validate_fhir_resource(data)
    if issues:
        return jsonify({'resourceType': 'OperationOutcome', 'issue': issues}), 400

    from models.medication import Prescription

    patient_id = (
        int(data.get('subject', {}).get('reference', '').split('/')[-1])
        if data.get('subject')
        else None
    )
    med_name = data.get('medicationCodeableConcept', {}).get('text', 'Unknown')
    import uuid

    rx = Prescription(
        tenant_id=getattr(g, 'tenant_id', None),
        patient_id=patient_id,
        prescription_number=f'RX-FHIR-{uuid.uuid4().hex[:8]}',
        diagnosis=med_name,
        notes=data.get('dosageInstruction', [{}])[0].get('text')
        if data.get('dosageInstruction')
        else None,
    )
    db.session.add(rx)
    safe_commit(db.session, error_message='commit', reraise=True)
    _log('CREATE', 'MedicationRequest', str(rx.id))
    return jsonify(
        {
            'resourceType': 'MedicationRequest',
            'id': str(rx.id),
            'status': 'active',
            'intent': 'order',
            'medicationCodeableConcept': {'text': med_name},
            'subject': {'reference': f'Patient/{patient_id}'},
        }
    ), 201


# --- _include/_revinclude support ---
def apply_include(entries, include_params, db_session):
    """Apply FHIR _include to bundle entries."""
    if not include_params:
        return entries
    # _include=Patient:general-practitioner
    for inc in include_params:
        parts = inc.split(':')
        if len(parts) >= 2:
            source_type, field = parts[0], parts[1]
            # Find referenced resources and add them
            for entry in list(entries):
                resource = entry.get('resource', {})
                if resource.get('resourceType') == source_type:
                    ref = resource.get(field, {})
                    if isinstance(ref, dict) and 'reference' in ref:
                        ref_str = ref['reference']
                        if '/' in ref_str:
                            _ref_type, _ref_id = ref_str.split('/', 1)
                            # Look up the referenced resource
                            pass  # Would need model lookup
    return entries


# --- FHIR Validation endpoint ---
@fhir_crud_bp.route('/$validate', methods=['POST'])
@login_required
@handle_route_errors
def fhir_validate():
    data = request.get_json() or {}
    issues = _validate_fhir_resource(data)
    if issues:
        return jsonify({'resourceType': 'OperationOutcome', 'issue': issues}), 400
    return jsonify(
        {
            'resourceType': 'OperationOutcome',
            'issue': [
                {
                    'severity': 'information',
                    'code': 'informational',
                    'details': {'text': 'Resource is valid'},
                }
            ],
        }
    )
