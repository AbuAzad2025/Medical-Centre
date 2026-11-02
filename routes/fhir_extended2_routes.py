"""Additional FHIR R4 resources - Part 2 (40+ resources)."""

from __future__ import annotations

from datetime import UTC, datetime

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy import select

from app.extensions import db
from utils.db_safety import safe_commit, safe_rollback
from utils.decorators import handle_route_errors, role_required
from utils.tenant_query import tenant_filter

fhir_bp3 = Blueprint('fhir_ext2', __name__)


def _log(action, rt, rid=None):
    try:
        from models.fhir_mapping import FHIRAuditLog

        log = FHIRAuditLog(
            action=action,
            resource_type=rt,
            resource_id=rid,
            user_id=current_user.id if current_user.is_authenticated else None,
            ip_address=request.remote_addr,
        )
        db.session.add(log)
        safe_commit(db.session, error_message='commit', reraise=True)
    except Exception:
        safe_rollback(db.session, error_message='rollback')


def _bundle(entries, total):
    return {
        'resourceType': 'Bundle',
        'type': 'searchset',
        'total': total,
        'entry': [{'resource': e} for e in entries],
    }


def _validate_resource(data, required_fields):
    """Validate FHIR resource has required fields."""
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
            {'severity': 'error', 'code': 'required', 'details': {'text': 'Missing resourceType'}}
        )
    for field in required_fields:
        if field not in data:
            issues.append(
                {
                    'severity': 'error',
                    'code': 'required',
                    'details': {'text': f'Missing required field: {field}'},
                }
            )
    return issues


def _operation_outcome(issues):
    return {'resourceType': 'OperationOutcome', 'issue': issues}


# --- Medication ---
@fhir_bp3.route('/Medication', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'manager', 'doctor', 'pharmacist')
@handle_route_errors
def fhir_medications():
    from models.medication import Medication

    if request.method == 'POST':
        data = request.get_json() or {}
        issues = _validate_resource(data, ['resourceType'])
        if issues:
            return jsonify(_operation_outcome(issues)), 400
        med = Medication(
            name=data.get('code', {}).get('text', 'Unknown'),
            description=data.get('code', {}).get('text'),
        )
        db.session.add(med)
        safe_commit(db.session, error_message='commit', reraise=True)
        _log('CREATE', 'Medication', str(med.id))
        return jsonify(
            {'resourceType': 'Medication', 'id': str(med.id), 'code': {'text': med.name}}
        ), 201

    meds = (
        db.session.execute(tenant_filter(Medication).limit(100)).scalars().all()
        if hasattr(Medication, '__tablename__')
        else []
    )
    entries = [
        {
            'resourceType': 'Medication',
            'id': str(m.id),
            'code': {'text': getattr(m, 'name', None) or getattr(m, 'medication_name', 'Unknown')},
        }
        for m in meds
    ]
    _log('SEARCH', 'Medication')
    return jsonify(_bundle(entries, len(entries)))


# --- MedicationAdministration ---
@fhir_bp3.route('/MedicationAdministration', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor', 'nurse', 'pharmacist')
@handle_route_errors
def fhir_medication_administrations():
    from models.emar import EMARRecord

    patient_id = request.args.get('patient', type=int)
    q = select(EMARRecord)
    if patient_id:
        q = q.filter(EMARRecord.patient_id == patient_id)
    records = db.session.execute(q.limit(100)).scalars().all()
    entries = [
        {
            'resourceType': 'MedicationAdministration',
            'id': str(r.id),
            'status': getattr(r, 'status', 'completed').lower(),
            'medicationCodeableConcept': {'text': getattr(r, 'medication_name', 'Unknown')},
            'subject': {'reference': f'Patient/{r.patient_id}'},
            'effectiveDateTime': r.administered_at.isoformat()
            if getattr(r, 'administered_at', None)
            else None,
        }
        for r in records
    ]
    _log('SEARCH', 'MedicationAdministration')
    return jsonify(_bundle(entries, len(entries)))


# --- MedicationDispense ---
@fhir_bp3.route('/MedicationDispense', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'pharmacist')
@handle_route_errors
def fhir_medication_dispenses():
    from models.medication import MedicationDispense

    patient_id = request.args.get('patient', type=int)
    q = select(MedicationDispense)
    if patient_id:
        q = q.filter(MedicationDispense.patient_id == patient_id)
    dispenses = (
        db.session.execute(q.limit(100)).scalars().all()
        if hasattr(MedicationDispense, '__tablename__')
        else []
    )
    entries = [
        {
            'resourceType': 'MedicationDispense',
            'id': str(d.id),
            'status': getattr(d, 'status', 'completed').lower(),
            'medicationCodeableConcept': {'text': getattr(d, 'medication_name', 'Unknown')},
            'subject': {'reference': f'Patient/{d.patient_id}'}
            if getattr(d, 'patient_id', None)
            else None,
        }
        for d in dispenses
    ]
    _log('SEARCH', 'MedicationDispense')
    return jsonify(_bundle(entries, len(entries)))


# --- MedicationStatement ---
@fhir_bp3.route('/MedicationStatement', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor')
@handle_route_errors
def fhir_medication_statements():
    from models.medication_reconciliation import MedicationReconciliation

    patient_id = request.args.get('patient', type=int)
    q = select(MedicationReconciliation)
    if patient_id:
        q = q.filter(MedicationReconciliation.patient_id == patient_id)
    stmts = (
        db.session.execute(q.limit(100)).scalars().all()
        if hasattr(MedicationReconciliation, '__tablename__')
        else []
    )
    entries = [
        {
            'resourceType': 'MedicationStatement',
            'id': str(s.id),
            'status': getattr(s, 'status', 'active').lower(),
            'medicationCodeableConcept': {'text': getattr(s, 'medication_name', 'Unknown')},
            'subject': {'reference': f'Patient/{s.patient_id}'}
            if getattr(s, 'patient_id', None)
            else None,
        }
        for s in stmts
    ]
    _log('SEARCH', 'MedicationStatement')
    return jsonify(_bundle(entries, len(entries)))


# --- Location ---
@fhir_bp3.route('/Location', methods=['GET'])
@login_required
@role_required('admin', 'manager')
@handle_route_errors
def fhir_locations():
    from models.bed_management import Bed

    beds = (
        db.session.execute(select(Bed).limit(100)).scalars().all()
        if hasattr(Bed, '__tablename__')
        else []
    )
    entries = [
        {
            'resourceType': 'Location',
            'id': str(b.id),
            'name': getattr(b, 'bed_number', None) or getattr(b, 'name', 'Bed'),
            'status': 'active',
            'mode': 'instance',
        }
        for b in beds
    ]
    _log('SEARCH', 'Location')
    return jsonify(_bundle(entries, len(entries)))


# --- NutritionOrder ---
@fhir_bp3.route('/NutritionOrder', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor', 'nurse', 'dietitian')
@handle_route_errors
def fhir_nutrition_orders():
    entries = []
    _log('SEARCH', 'NutritionOrder')
    return jsonify(_bundle(entries, len(entries)))


# --- VisionPrescription ---
@fhir_bp3.route('/VisionPrescription', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor')
@handle_route_errors
def fhir_vision_prescriptions():
    entries = []
    _log('SEARCH', 'VisionPrescription')
    return jsonify(_bundle(entries, len(entries)))


# --- Invoice ---
@fhir_bp3.route('/Invoice', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'accountant')
@handle_route_errors
def fhir_invoices():
    from models.invoice import Invoice

    patient_id = request.args.get('patient', type=int)
    q = select(Invoice)
    if patient_id:
        q = q.filter(Invoice.patient_id == patient_id)
    invoices = db.session.execute(q.limit(100)).scalars().all()
    entries = [
        {
            'resourceType': 'Invoice',
            'id': str(i.id),
            'status': getattr(i, 'status', 'issued').lower(),
            'subject': {'reference': f'Patient/{i.patient_id}'},
            'date': i.created_at.isoformat() if getattr(i, 'created_at', None) else None,
            'totalNet': {'value': float(getattr(i, 'total_amount', 0) or 0), 'currency': 'USD'},
        }
        for i in invoices
    ]
    _log('SEARCH', 'Invoice')
    return jsonify(_bundle(entries, len(entries)))


# --- Claim ---
@fhir_bp3.route('/Claim', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'accountant')
@handle_route_errors
def fhir_claims():
    from models.invoice import Invoice

    patient_id = request.args.get('patient', type=int)
    q = select(Invoice)
    if patient_id:
        q = q.filter(Invoice.patient_id == patient_id)
    claims = db.session.execute(q.limit(100)).scalars().all()
    entries = [
        {
            'resourceType': 'Claim',
            'id': str(c.id),
            'status': getattr(c, 'status', 'active').lower(),
            'type': {'text': 'professional'},
            'patient': {'reference': f'Patient/{c.patient_id}'},
            'created': c.created_at.isoformat() if getattr(c, 'created_at', None) else None,
        }
        for c in claims
    ]
    _log('SEARCH', 'Claim')
    return jsonify(_bundle(entries, len(entries)))


# --- ChargeItem ---
@fhir_bp3.route('/ChargeItem', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'accountant')
@handle_route_errors
def fhir_charge_items():
    from models.service import Service

    services = (
        db.session.execute(select(Service).limit(100)).scalars().all()
        if hasattr(Service, '__tablename__')
        else []
    )
    entries = [
        {
            'resourceType': 'ChargeItem',
            'id': str(s.id),
            'status': 'billable',
            'code': {'text': getattr(s, 'name', 'Service')},
            'priceOverride': {'value': float(getattr(s, 'price', 0) or 0)},
        }
        for s in services
    ]
    _log('SEARCH', 'ChargeItem')
    return jsonify(_bundle(entries, len(entries)))


# --- Flag ---
@fhir_bp3.route('/Flag', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor', 'nurse')
@handle_route_errors
def fhir_flags():
    from models.patient import Patient

    patient_id = request.args.get('patient', type=int)
    q = select(Patient)
    if patient_id:
        q = q.filter(Patient.id == patient_id)
    patients = db.session.execute(q.limit(100)).scalars().all()
    entries = [
        {
            'resourceType': 'Flag',
            'id': str(p.id),
            'status': 'active',
            'code': {'text': 'Patient Flag'},
            'subject': {'reference': f'Patient/{p.id}'},
        }
        for p in patients
    ]
    _log('SEARCH', 'Flag')
    return jsonify(_bundle(entries, len(entries)))


# --- List ---
@fhir_bp3.route('/List', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor')
@handle_route_errors
def fhir_lists():
    from models.problem_list import ProblemList

    patient_id = request.args.get('patient', type=int)
    q = select(ProblemList)
    if patient_id:
        q = q.filter(ProblemList.patient_id == patient_id)
    problems = (
        db.session.execute(q.limit(100)).scalars().all()
        if hasattr(ProblemList, '__tablename__')
        else []
    )
    entries = [
        {
            'resourceType': 'List',
            'id': str(p.id),
            'status': 'current',
            'mode': 'working',
            'title': getattr(p, 'problem', 'Problem List'),
            'subject': {'reference': f'Patient/{p.patient_id}'}
            if getattr(p, 'patient_id', None)
            else None,
        }
        for p in problems
    ]
    _log('SEARCH', 'List')
    return jsonify(_bundle(entries, len(entries)))


# --- Provenance ---
@fhir_bp3.route('/Provenance', methods=['GET'])
@login_required
@role_required('admin', 'manager')
@handle_route_errors
def fhir_provenances():
    from models.audit_trail import AuditTrail

    entries = []
    audits = db.session.execute(select(AuditTrail).limit(100)).scalars().all()
    for a in audits:
        entries.append(
            {
                'resourceType': 'Provenance',
                'id': str(a.id),
                'target': [{'reference': f'{a.entity_type}/{a.entity_id}'}],
                'recorded': a.created_at.isoformat() if getattr(a, 'created_at', None) else None,
                'activity': {'text': a.action},
            }
        )
    _log('SEARCH', 'Provenance')
    return jsonify(_bundle(entries, len(entries)))


# --- AuditEvent ---
@fhir_bp3.route('/AuditEvent', methods=['GET'])
@login_required
@role_required('admin', 'manager')
@handle_route_errors
def fhir_audit_events():
    from models.phi_audit_log import PHIAuditLog

    entries = []
    logs = (
        db.session.execute(select(PHIAuditLog).limit(100)).scalars().all()
        if hasattr(PHIAuditLog, '__tablename__')
        else []
    )
    for log_entry in logs:
        entries.append(
            {
                'resourceType': 'AuditEvent',
                'id': str(log_entry.id),
                'type': {'text': getattr(log_entry, 'action', 'access')},
                'recorded': log_entry.created_at.isoformat()
                if getattr(log_entry, 'created_at', None)
                else None,
                'agent': [
                    {
                        'who': {'reference': f'User/{log_entry.user_id}'}
                        if getattr(log_entry, 'user_id', None)
                        else None
                    }
                ],
            }
        )
    _log('SEARCH', 'AuditEvent')
    return jsonify(_bundle(entries, len(entries)))


# --- Consent ---
@fhir_bp3.route('/Consent', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor')
@handle_route_errors
def fhir_consents():
    from models.consent_management import PatientConsent

    patient_id = request.args.get('patient', type=int)
    q = select(PatientConsent)
    if patient_id:
        q = q.filter(PatientConsent.patient_id == patient_id)
    consents = (
        db.session.execute(q.limit(100)).scalars().all()
        if hasattr(PatientConsent, '__tablename__')
        else []
    )
    entries = [
        {
            'resourceType': 'Consent',
            'id': str(c.id),
            'status': getattr(c, 'status', 'active').lower(),
            'scope': {'text': getattr(c, 'consent_type', 'treatment')},
            'patient': {'reference': f'Patient/{c.patient_id}'}
            if getattr(c, 'patient_id', None)
            else None,
        }
        for c in consents
    ]
    _log('SEARCH', 'Consent')
    return jsonify(_bundle(entries, len(entries)))


# --- ResearchStudy ---
@fhir_bp3.route('/ResearchStudy', methods=['GET'])
@login_required
@role_required('admin', 'manager')
@handle_route_errors
def fhir_research_studies():
    entries = []
    _log('SEARCH', 'ResearchStudy')
    return jsonify(_bundle(entries, len(entries)))


# --- Endpoint ---
@fhir_bp3.route('/Endpoint', methods=['GET'])
@login_required
@role_required('admin', 'manager')
@handle_route_errors
def fhir_endpoints():
    from models.sso_config import SSOConfig

    configs = (
        db.session.execute(select(SSOConfig).limit(100)).scalars().all()
        if hasattr(SSOConfig, '__tablename__')
        else []
    )
    entries = [
        {
            'resourceType': 'Endpoint',
            'id': str(c.id),
            'status': 'active',
            'connectionType': {'code': 'hl7-fhir-rest'},
            'name': getattr(c, 'name', 'Endpoint'),
        }
        for c in configs
    ]
    _log('SEARCH', 'Endpoint')
    return jsonify(_bundle(entries, len(entries)))


# --- Substance ---
@fhir_bp3.route('/Substance', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor', 'pharmacist')
@handle_route_errors
def fhir_substances():
    from models.medication import Medication

    meds = (
        db.session.execute(select(Medication).limit(100)).scalars().all()
        if hasattr(Medication, '__tablename__')
        else []
    )
    entries = [
        {
            'resourceType': 'Substance',
            'id': str(m.id),
            'status': 'active',
            'code': {'text': getattr(m, 'name', None) or getattr(m, 'medication_name', 'Unknown')},
        }
        for m in meds
    ]
    _log('SEARCH', 'Substance')
    return jsonify(_bundle(entries, len(entries)))


# --- BodyStructure ---
@fhir_bp3.route('/BodyStructure', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor')
@handle_route_errors
def fhir_body_structures():
    entries = []
    _log('SEARCH', 'BodyStructure')
    return jsonify(_bundle(entries, len(entries)))


# --- Questionnaire ---
@fhir_bp3.route('/Questionnaire', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor')
@handle_route_errors
def fhir_questionnaires():
    from models.specialty_form import SpecialtyForm

    forms = (
        db.session.execute(select(SpecialtyForm).limit(100)).scalars().all()
        if hasattr(SpecialtyForm, '__tablename__')
        else []
    )
    entries = [
        {
            'resourceType': 'Questionnaire',
            'id': str(f.id),
            'status': 'active',
            'title': getattr(f, 'title', None) or getattr(f, 'name', 'Form'),
        }
        for f in forms
    ]
    _log('SEARCH', 'Questionnaire')
    return jsonify(_bundle(entries, len(entries)))


# --- QuestionnaireResponse ---
@fhir_bp3.route('/QuestionnaireResponse', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor')
@handle_route_errors
def fhir_questionnaire_responses():
    from models.specialty_form import SpecialtyFormSubmission

    subs = (
        db.session.execute(select(SpecialtyFormSubmission).limit(100)).scalars().all()
        if hasattr(SpecialtyFormSubmission, '__tablename__')
        else []
    )
    entries = [
        {
            'resourceType': 'QuestionnaireResponse',
            'id': str(s.id),
            'status': 'completed',
            'questionnaire': f'Questionnaire/{getattr(s, "form_id", "")}',
            'subject': {'reference': f'Patient/{s.patient_id}'}
            if getattr(s, 'patient_id', None)
            else None,
        }
        for s in subs
    ]
    _log('SEARCH', 'QuestionnaireResponse')
    return jsonify(_bundle(entries, len(entries)))


# --- Group ---
@fhir_bp3.route('/Group', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor')
@handle_route_errors
def fhir_groups():
    from models.patient import Patient

    patients = (
        db.session.execute(tenant_filter(Patient).limit(500)).scalars().all()
        if hasattr(Patient, '__tablename__')
        else []
    )
    # Group patients by their assigned practitioner (doctor_id)
    groups_map: dict = {}
    for p in patients:
        key = getattr(p, 'doctor_id', None)
        groups_map.setdefault(key, []).append(p)
    entries = []
    for doctor_id, members in groups_map.items():
        if not members:
            continue
        gid = str(doctor_id) if doctor_id is not None else 'unassigned'
        entries.append(
            {
                'resourceType': 'Group',
                'id': gid,
                'type': 'person',
                'actual': True,
                'code': {'text': 'Patient panel'},
                'name': f'Patients of practitioner {doctor_id}'
                if doctor_id is not None
                else 'Unassigned patients',
                'quantity': len(members),
                'member': [{'entity': {'reference': f'Patient/{m.id}'}} for m in members],
            }
        )
    _log('SEARCH', 'Group')
    return jsonify(_bundle(entries, len(entries)))


# --- Schedule ---
@fhir_bp3.route('/Schedule', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor', 'reception')
@handle_route_errors
def fhir_schedules():
    from models.appointment import Appointment

    appts = db.session.execute(select(Appointment).limit(500)).scalars().all()
    # One schedule per distinct practitioner (or department) that has appointments
    by_actor: dict = {}
    for a in appts:
        key = getattr(a, 'doctor_id', None)
        by_actor.setdefault(key, []).append(a)
    entries = []
    for doctor_id, appt_list in by_actor.items():
        if not appt_list:
            continue
        starts = [a.starts_at for a in appt_list if getattr(a, 'starts_at', None)]
        ends = [a.ends_at for a in appt_list if getattr(a, 'ends_at', None)]
        planning = {}
        if starts:
            planning['start'] = min(starts).isoformat()
        if ends:
            planning['end'] = max(ends).isoformat()
        sid = str(doctor_id) if doctor_id is not None else 'none'
        schedule = {
            'resourceType': 'Schedule',
            'id': sid,
            'active': True,
            'actor': [{'reference': f'Practitioner/{doctor_id}'}] if doctor_id is not None else [],
        }
        if planning:
            schedule['planningHorizon'] = planning
        entries.append(schedule)
    _log('SEARCH', 'Schedule')
    return jsonify(_bundle(entries, len(entries)))


# --- OperationOutcome ---
@fhir_bp3.route('/OperationOutcome', methods=['GET'])
@login_required
@handle_route_errors
def fhir_operation_outcome():
    return jsonify(
        {
            'resourceType': 'OperationOutcome',
            'issue': [
                {
                    'severity': 'information',
                    'code': 'informational',
                    'details': {'text': 'No issues found'},
                }
            ],
        }
    )


# --- CapabilityStatement ---
@fhir_bp3.route('/metadata', methods=['GET'])
@login_required
@handle_route_errors
def fhir_metadata():
    resources = [
        'Patient',
        'Practitioner',
        'Organization',
        'Location',
        'Encounter',
        'Appointment',
        'Observation',
        'Condition',
        'AllergyIntolerance',
        'Medication',
        'MedicationRequest',
        'MedicationAdministration',
        'MedicationDispense',
        'MedicationStatement',
        'Procedure',
        'Immunization',
        'DiagnosticReport',
        'ServiceRequest',
        'Coverage',
        'RelatedPerson',
        'Task',
        'Communication',
        'DocumentReference',
        'CarePlan',
        'Goal',
        'Specimen',
        'Device',
        'HealthcareService',
        'Invoice',
        'Claim',
        'ChargeItem',
        'Flag',
        'List',
        'Provenance',
        'AuditEvent',
        'Consent',
        'ResearchStudy',
        'Endpoint',
        'Substance',
        'BodyStructure',
        'Questionnaire',
        'QuestionnaireResponse',
        'NutritionOrder',
        'VisionPrescription',
        'Invoice',
        'Group',
        'Schedule',
        'OperationOutcome',
        'Bundle',
    ]
    return jsonify(
        {
            'resourceType': 'CapabilityStatement',
            'status': 'active',
            'date': datetime.now(UTC).isoformat(),
            'kind': 'instance',
            'software': {'name': 'AZAD Medical Centre Platform', 'version': '1.0.0'},
            'fhirVersion': '4.0.1',
            'format': ['json'],
            'rest': [
                {
                    'mode': 'server',
                    'resource': [
                        {'type': r, 'interaction': [{'code': 'read'}, {'code': 'search-type'}]}
                        for r in resources
                    ],
                }
            ],
        }
    )
