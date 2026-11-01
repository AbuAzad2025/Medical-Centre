"""HL7 FHIR R4 API - Expanded resource endpoints."""
from __future__ import annotations

from datetime import UTC, datetime

from flask import Blueprint, abort, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from utils.db_safety import safe_commit, safe_rollback
from utils.decorators import handle_route_errors, role_required
from utils.tenant_query import get_tenant_record, tenant_filter

fhir_bp2 = Blueprint('fhir_ext', __name__)


def _log(action, rt, rid=None):
    try:
        from models.fhir_mapping import FHIRAuditLog
        log = FHIRAuditLog(action=action, resource_type=rt, resource_id=rid,
                           user_id=current_user.id if current_user.is_authenticated else None,
                           ip_address=request.remote_addr)
        db.session.add(log)
        safe_commit(db.session, error_message='commit', reraise=True)
    except Exception:
        safe_rollback(db.session, error_message='rollback')


def _bundle(entries, total):
    return {'resourceType': 'Bundle', 'type': 'searchset', 'total': total,
            'entry': [{'resource': e} for e in entries]}


# --- Practitioner ---
@fhir_bp2.route('/Practitioner', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor')
@handle_route_errors
def fhir_practitioners():
    from models.user import User
    users = db.session.execute(tenant_filter(User).filter_by(is_active=True).limit(100)).scalars().all()
    entries = [{'resourceType': 'Practitioner', 'id': str(u.id),
                'name': [{'text': u.full_name}], 'active': u.is_active} for u in users]
    _log('SEARCH', 'Practitioner')
    return jsonify(_bundle(entries, len(entries)))


@fhir_bp2.route('/Practitioner/<int:pid>', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor')
@handle_route_errors
def fhir_practitioner(pid):
    from models.user import User
    u = get_tenant_record(User, pid)
    if not u:
        abort(404)
    _log('READ', 'Practitioner', str(pid))
    return jsonify({'resourceType': 'Practitioner', 'id': str(u.id),
                    'name': [{'text': u.full_name}], 'active': u.is_active})


# --- Organization ---
@fhir_bp2.route('/Organization', methods=['GET'])
@login_required
@role_required('admin', 'manager')
@handle_route_errors
def fhir_organizations():
    from app.core.tenant.models import Tenant
    tenants = db.session.execute(select(Tenant).limit(100)).scalars().all()
    entries = [{'resourceType': 'Organization', 'id': str(t.id), 'name': t.name,
                'active': t.status == 'ACTIVE'} for t in tenants]
    _log('SEARCH', 'Organization')
    return jsonify(_bundle(entries, len(entries)))


# --- Appointment ---
@fhir_bp2.route('/Appointment', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor', 'reception')
@handle_route_errors
def fhir_appointments():
    from models.appointment import Appointment
    patient_id = request.args.get('patient', type=int)
    q = select(Appointment)
    if patient_id:
        q = q.filter(Appointment.patient_id == patient_id)
    appts = db.session.execute(q.limit(100)).scalars().all()
    entries = [{'resourceType': 'Appointment', 'id': str(a.id),
                'status': getattr(a, 'status', 'booked').lower(),
                'start': getattr(a, 'scheduled_start', None).isoformat() if getattr(a, 'scheduled_start', None) else None,
                'end': getattr(a, 'scheduled_end', None).isoformat() if getattr(a, 'scheduled_end', None) else None,
                'participant': [{'actor': {'reference': f'Patient/{a.patient_id}'}}]} for a in appts]
    _log('SEARCH', 'Appointment')
    return jsonify(_bundle(entries, len(entries)))


# --- AllergyIntolerance ---
@fhir_bp2.route('/AllergyIntolerance', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor', 'nurse')
@handle_route_errors
def fhir_allergies():
    from models.allergy import Allergy
    patient_id = request.args.get('patient', type=int)
    q = select(Allergy)
    if patient_id:
        q = q.filter(Allergy.patient_id == patient_id)
    allergies = db.session.execute(q.limit(100)).scalars().all()
    entries = [{'resourceType': 'AllergyIntolerance', 'id': str(a.id),
                'clinicalStatus': {'coding': [{'code': 'active'}]},
                'code': {'text': getattr(a, 'allergen', 'Unknown')},
                'patient': {'reference': f'Patient/{a.patient_id}'},
                'recordedDate': a.created_at.isoformat() if getattr(a, 'created_at', None) else None} for a in allergies]
    _log('SEARCH', 'AllergyIntolerance')
    return jsonify(_bundle(entries, len(entries)))


# --- Procedure ---
@fhir_bp2.route('/Procedure', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor')
@handle_route_errors
def fhir_procedures():
    from models.medical_record import MedicalRecord
    patient_id = request.args.get('patient', type=int)
    q = select(MedicalRecord)
    if patient_id:
        q = q.filter(MedicalRecord.patient_id == patient_id)
    records = db.session.execute(q.limit(100)).scalars().all()
    entries = [{'resourceType': 'Procedure', 'id': str(r.id),
                'status': 'completed',
                'code': {'text': getattr(r, 'procedure', None) or getattr(r, 'chief_complaint', 'Unknown')},
                'subject': {'reference': f'Patient/{r.patient_id}'},
                'performedDateTime': r.created_at.isoformat() if getattr(r, 'created_at', None) else None} for r in records]
    _log('SEARCH', 'Procedure')
    return jsonify(_bundle(entries, len(entries)))


# --- Immunization ---
@fhir_bp2.route('/Immunization', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor', 'nurse')
@handle_route_errors
def fhir_immunizations():
    from models.vaccination import Vaccination
    patient_id = request.args.get('patient', type=int)
    q = select(Vaccination)
    if patient_id:
        q = q.filter(Vaccination.patient_id == patient_id)
    vax = db.session.execute(q.limit(100)).scalars().all()
    entries = [{'resourceType': 'Immunization', 'id': str(v.id),
                'status': 'completed',
                'vaccineCode': {'text': getattr(v, 'vaccine_name', 'Unknown')},
                'patient': {'reference': f'Patient/{v.patient_id}'},
                'occurrenceDateTime': v.administered_date.isoformat() if getattr(v, 'administered_date', None) else None} for v in vax]
    _log('SEARCH', 'Immunization')
    return jsonify(_bundle(entries, len(entries)))


# --- DiagnosticReport ---
@fhir_bp2.route('/DiagnosticReport', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor')
@handle_route_errors
def fhir_diagnostic_reports():
    from models.lab_request import LabRequest
    patient_id = request.args.get('patient', type=int)
    q = select(LabRequest)
    if patient_id:
        q = q.filter(LabRequest.patient_id == patient_id)
    reports = db.session.execute(q.limit(100)).scalars().all()
    entries = [{'resourceType': 'DiagnosticReport', 'id': str(r.id),
                'status': getattr(r, 'status', 'final').lower(),
                'code': {'text': getattr(r, 'test_name', 'Lab Report')},
                'subject': {'reference': f'Patient/{r.patient_id}'},
                'issued': r.created_at.isoformat() if getattr(r, 'created_at', None) else None} for r in reports]
    _log('SEARCH', 'DiagnosticReport')
    return jsonify(_bundle(entries, len(entries)))


# --- ServiceRequest ---
@fhir_bp2.route('/ServiceRequest', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor')
@handle_route_errors
def fhir_service_requests():
    from models.lab_request import LabRequest
    patient_id = request.args.get('patient', type=int)
    q = select(LabRequest)
    if patient_id:
        q = q.filter(LabRequest.patient_id == patient_id)
    reqs = db.session.execute(q.limit(100)).scalars().all()
    entries = [{'resourceType': 'ServiceRequest', 'id': str(r.id),
                'status': getattr(r, 'status', 'active').lower(),
                'intent': 'order',
                'code': {'text': getattr(r, 'test_name', 'Lab Test')},
                'subject': {'reference': f'Patient/{r.patient_id}'},
                'authoredOn': r.created_at.isoformat() if getattr(r, 'created_at', None) else None} for r in reqs]
    _log('SEARCH', 'ServiceRequest')
    return jsonify(_bundle(entries, len(entries)))


# --- Coverage ---
@fhir_bp2.route('/Coverage', methods=['GET'])
@login_required
@role_required('admin', 'manager')
@handle_route_errors
def fhir_coverages():
    from models.insurance import Insurance
    patient_id = request.args.get('patient', type=int)
    q = select(Insurance)
    if patient_id:
        q = q.filter(Insurance.patient_id == patient_id)
    coverages = db.session.execute(q.limit(100)).scalars().all()
    entries = [{'resourceType': 'Coverage', 'id': str(c.id),
                'status': 'active',
                'type': {'text': getattr(c, 'insurance_type', 'Insurance')},
                'beneficiary': {'reference': f'Patient/{c.patient_id}'},
                'payor': [{'display': getattr(c, 'provider_name', 'Unknown')}]} for c in coverages]
    _log('SEARCH', 'Coverage')
    return jsonify(_bundle(entries, len(entries)))


# --- RelatedPerson ---
@fhir_bp2.route('/RelatedPerson', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor', 'reception')
@handle_route_errors
def fhir_related_persons():
    from models.relationships_map import PatientRelationship
    patient_id = request.args.get('patient', type=int)
    q = select(PatientRelationship)
    if patient_id:
        q = q.filter(PatientRelationship.patient_id == patient_id)
    rels = db.session.execute(q.limit(100)).scalars().all()
    entries = [{'resourceType': 'RelatedPerson', 'id': str(r.id),
                'patient': {'reference': f'Patient/{r.patient_id}'},
                'relationship': [{'text': getattr(r, 'relationship_type', 'Unknown')}],
                'name': [{'text': getattr(r, 'related_person_name', 'Unknown')}]} for r in rels]
    _log('SEARCH', 'RelatedPerson')
    return jsonify(_bundle(entries, len(entries)))


# --- Task ---
@fhir_bp2.route('/Task', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor', 'nurse')
@handle_route_errors
def fhir_tasks():
    from models.task_management import Task
    status = request.args.get('status', '')
    q = select(Task)
    if status:
        q = q.filter(Task.status.ilike(status))
    tasks = db.session.execute(q.limit(100)).scalars().all()
    entries = [{'resourceType': 'Task', 'id': str(t.id),
                'status': getattr(t, 'status', 'requested').lower(),
                'intent': 'order',
                'description': getattr(t, 'description', None) or getattr(t, 'title', 'Task'),
                'for': {'reference': f'Patient/{t.patient_id}'} if getattr(t, 'patient_id', None) else None} for t in tasks]
    _log('SEARCH', 'Task')
    return jsonify(_bundle(entries, len(entries)))


# --- Communication ---
@fhir_bp2.route('/Communication', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor', 'nurse')
@handle_route_errors
def fhir_communications():
    from models.notification import Notification
    patient_id = request.args.get('patient', type=int)
    q = select(Notification)
    if patient_id:
        q = q.filter(Notification.patient_id == patient_id)
    comms = db.session.execute(q.limit(100)).scalars().all()
    entries = [{'resourceType': 'Communication', 'id': str(c.id),
                'status': 'completed',
                'subject': {'reference': f'Patient/{c.patient_id}'} if getattr(c, 'patient_id', None) else None,
                'sent': c.created_at.isoformat() if getattr(c, 'created_at', None) else None,
                'payload': [{'contentString': getattr(c, 'message', None) or getattr(c, 'title', '')}]} for c in comms]
    _log('SEARCH', 'Communication')
    return jsonify(_bundle(entries, len(entries)))


# --- DocumentReference ---
@fhir_bp2.route('/DocumentReference', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor')
@handle_route_errors
def fhir_document_references():
    from models.medical_record import MedicalRecord
    patient_id = request.args.get('patient', type=int)
    q = select(MedicalRecord)
    if patient_id:
        q = q.filter(MedicalRecord.patient_id == patient_id)
    records = db.session.execute(q.limit(100)).scalars().all()
    entries = [{'resourceType': 'DocumentReference', 'id': str(r.id),
                'status': 'current',
                'type': {'text': getattr(r, 'record_type', 'Clinical Note')},
                'subject': {'reference': f'Patient/{r.patient_id}'},
                'date': r.created_at.isoformat() if getattr(r, 'created_at', None) else None,
                'content': [{'attachment': {'title': getattr(r, 'title', 'Medical Record')}}]} for r in records]
    _log('SEARCH', 'DocumentReference')
    return jsonify(_bundle(entries, len(entries)))


# --- CarePlan ---
@fhir_bp2.route('/CarePlan', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor')
@handle_route_errors
def fhir_care_plans():
    from models.clinical_pathway import ClinicalPathway
    patient_id = request.args.get('patient', type=int)
    q = select(ClinicalPathway)
    if patient_id:
        q = q.filter(ClinicalPathway.patient_id == patient_id)
    plans = db.session.execute(q.limit(100)).scalars().all()
    entries = [{'resourceType': 'CarePlan', 'id': str(p.id),
                'status': getattr(p, 'status', 'active').lower(),
                'intent': 'plan',
                'title': getattr(p, 'title', None) or getattr(p, 'name', 'Care Plan'),
                'subject': {'reference': f'Patient/{p.patient_id}'} if getattr(p, 'patient_id', None) else None} for p in plans]
    _log('SEARCH', 'CarePlan')
    return jsonify(_bundle(entries, len(entries)))


# --- Goal ---
@fhir_bp2.route('/Goal', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor')
@handle_route_errors
def fhir_goals():
    from models.treatment import Treatment
    patient_id = request.args.get('patient', type=int)
    q = select(Treatment)
    if patient_id:
        q = q.filter(Treatment.patient_id == patient_id)
    treatments = db.session.execute(q.limit(100)).scalars().all()
    entries = [{'resourceType': 'Goal', 'id': str(t.id),
                'lifecycleStatus': 'active',
                'description': {'text': getattr(t, 'description', None) or getattr(t, 'name', 'Treatment Goal')},
                'subject': {'reference': f'Patient/{t.patient_id}'} if getattr(t, 'patient_id', None) else None} for t in treatments]
    _log('SEARCH', 'Goal')
    return jsonify(_bundle(entries, len(entries)))


# --- Specimen ---
@fhir_bp2.route('/Specimen', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor', 'lab')
@handle_route_errors
def fhir_specimens():
    from models.lab_request import LabRequest
    patient_id = request.args.get('patient', type=int)
    q = select(LabRequest)
    if patient_id:
        q = q.filter(LabRequest.patient_id == patient_id)
    reqs = db.session.execute(q.limit(100)).scalars().all()
    entries = [{'resourceType': 'Specimen', 'id': str(r.id),
                'status': 'available',
                'type': {'text': getattr(r, 'specimen_type', 'Blood')},
                'subject': {'reference': f'Patient/{r.patient_id}'}} for r in reqs]
    _log('SEARCH', 'Specimen')
    return jsonify(_bundle(entries, len(entries)))


# --- Device ---
@fhir_bp2.route('/Device', methods=['GET'])
@login_required
@role_required('admin', 'manager')
@handle_route_errors
def fhir_devices():
    from models.barcode_tracking import BarcodeDevice
    devices = db.session.execute(select(BarcodeDevice).limit(100)).scalars().all() if hasattr(BarcodeDevice, '__tablename__') else []
    entries = [{'resourceType': 'Device', 'id': str(d.id),
                'status': 'active',
                'deviceName': [{'name': getattr(d, 'name', 'Device'), 'type': 'user-friendly-name'}]} for d in devices]
    _log('SEARCH', 'Device')
    return jsonify(_bundle(entries, len(entries)))


# --- HealthcareService ---
@fhir_bp2.route('/HealthcareService', methods=['GET'])
@login_required
@role_required('admin', 'manager')
@handle_route_errors
def fhir_healthcare_services():
    from models.department import Department
    depts = db.session.execute(tenant_filter(Department).limit(100)).scalars().all()
    entries = [{'resourceType': 'HealthcareService', 'id': str(d.id),
                'active': True,
                'name': getattr(d, 'name', 'Department'),
                'type': [{'text': getattr(d, 'name', 'Service')}]} for d in depts]
    _log('SEARCH', 'HealthcareService')
    return jsonify(_bundle(entries, len(entries)))


# --- CapabilityStatement ---
@fhir_bp2.route('/metadata', methods=['GET'])
def fhir_metadata():
    resources = [
        'Patient', 'Practitioner', 'Organization', 'Location', 'Encounter',
        'Appointment', 'Observation', 'Condition', 'AllergyIntolerance',
        'MedicationRequest', 'MedicationAdministration', 'Procedure',
        'Immunization', 'DiagnosticReport', 'ServiceRequest', 'Coverage',
        'RelatedPerson', 'Task', 'Communication', 'DocumentReference',
        'CarePlan', 'Goal', 'Specimen', 'Device', 'HealthcareService',
        'Invoice', 'Claim', 'Bundle', 'OperationOutcome',
    ]
    return jsonify({
        'resourceType': 'CapabilityStatement',
        'status': 'active',
        'date': datetime.now(UTC).isoformat(),
        'kind': 'instance',
        'software': {'name': 'AZAD Medical Centre Platform', 'version': '1.0.0'},
        'fhirVersion': '4.0.1',
        'format': ['json'],
        'rest': [{'mode': 'server', 'resource': [
            {'type': r, 'interaction': [{'code': 'read'}, {'code': 'search-type'}]} for r in resources
        ]}],
    })
