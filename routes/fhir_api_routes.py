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
from utils.tenant_query import TenantContextError, get_tenant_record, tenant_filter

fhir_bp = Blueprint('fhir', __name__)


def _patient_or_404(patient_id):
    """FHIR read of a missing resource must be 404, not a redirect."""
    try:
        patient = get_tenant_record(Patient, patient_id)
    except TenantContextError:
        abort(404)
    if patient is None:
        abort(404)
    return patient


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
    from utils.fhir_search import apply_fhir_pagination, apply_fhir_sort

    name = request.args.get('name', '')
    gender = request.args.get('gender', '')
    birthdate = request.args.get('birthdate', '')

    query = tenant_filter(Patient)
    if gender:
        query = query.filter(Patient.gender.ilike(gender))
    if birthdate:
        query = query.filter(Patient.birth_date == birthdate)

    sort_param = request.args.get('_sort')

    if name:
        # Patient.full_name is a Python-side decrypting property, not a
        # column; using .ilike on it raised AttributeError and every name
        # search answered 500. Filter the tenant-scoped rows in Python
        # instead, then sort and paginate in memory.
        rows = db.session.execute(query).scalars().all()
        needle = name.lower()
        rows = [p for p in rows if needle in (p.full_name or '').lower()]
        if sort_param:
            descending = sort_param.startswith('-')
            field = sort_param[1:] if descending else sort_param

            def _key(p, field=field):
                value = getattr(p, field, '') or ''
                try:
                    return str(value).lower()
                except Exception:
                    return ''

            rows.sort(key=_key, reverse=descending)
        try:
            count = min(int(request.args.get('_count', 20)), 100)
            offset = int(request.args.get('_offset', 0))
        except (TypeError, ValueError):
            count, offset = 20, 0
        total = len(rows)
        patients = rows[offset : offset + count]
    else:
        total = query.count()
        query = apply_fhir_sort(query, Patient, sort_param)
        query, _count, _offset = apply_fhir_pagination(query, request)
        patients = db.session.execute(query).scalars().all()

    # _include support
    include_params = request.args.getlist('_include')
    revinclude_params = request.args.getlist('_revinclude')
    entries = [
        {
            'resource': {
                'resourceType': 'Patient',
                'id': str(p.id),
                'name': [{'text': p.full_name}],
                'gender': p.gender.lower() if p.gender else 'unknown',
                'birthDate': p.birth_date.isoformat() if p.birth_date else None,
                'generalPractitioner': [{'reference': f'Practitioner/{p.doctor_id}'}]
                if getattr(p, 'doctor_id', None)
                else [],
            },
            'search': {'mode': 'match'},
        }
        for p in patients
    ]

    # _include: Patient:general-practitioner
    if (
        'Patient:general-practitioner' in include_params
        or 'Patient:generalPractitioner' in include_params
    ):
        for p in patients:
            if getattr(p, 'doctor_id', None):
                from models.user import User

                doc = db.session.get(User, p.doctor_id)
                if doc:
                    entries.append(
                        {
                            'resource': {
                                'resourceType': 'Practitioner',
                                'id': str(doc.id),
                                'name': [{'text': doc.full_name}],
                            },
                            'search': {'mode': 'include'},
                        }
                    )

    # _revinclude support
    patient_ids = [p.id for p in patients]
    if 'Observation:patient' in revinclude_params:
        from sqlalchemy import select as _select

        from models.lab_request import LabResult

        lab_results = (
            (
                db.session.execute(
                    _select(LabResult).filter(LabResult.patient_id.in_(patient_ids)).limit(200)
                )
                .scalars()
                .all()
            )
            if patient_ids
            else []
        )
        for lr in lab_results:
            entries.append(
                {
                    'resource': {
                        'resourceType': 'Observation',
                        'id': f'lab-{lr.id}',
                        'status': 'final',
                        'code': {'text': lr.test_name},
                        'subject': {'reference': f'Patient/{lr.patient_id}'},
                        'valueString': lr.value,
                    },
                    'search': {'mode': 'include'},
                }
            )

    if 'Condition:patient' in revinclude_params:
        from sqlalchemy import select as _select

        from models.medical_record import MedicalRecord

        records = (
            (
                db.session.execute(
                    _select(MedicalRecord)
                    .filter(MedicalRecord.patient_id.in_(patient_ids))
                    .limit(200)
                )
                .scalars()
                .all()
            )
            if patient_ids
            else []
        )
        for rec in records:
            entries.append(
                {
                    'resource': {
                        'resourceType': 'Condition',
                        'id': str(rec.id),
                        'clinicalStatus': {
                            'coding': [
                                {
                                    'system': 'http://terminology.hl7.org/CodeSystem/condition-clinical',
                                    'code': 'active',
                                }
                            ]
                        },
                        'code': {
                            'text': getattr(rec, 'diagnosis', None)
                            or getattr(rec, 'chief_complaint', 'Unknown')
                        },
                        'subject': {'reference': f'Patient/{rec.patient_id}'},
                        'recordedDate': rec.created_at.isoformat() if rec.created_at else None,
                    },
                    'search': {'mode': 'include'},
                }
            )

    _log_fhir_access('SEARCH', 'Patient')
    return jsonify(
        {
            'resourceType': 'Bundle',
            'type': 'searchset',
            'total': total,
            'entry': entries,
            'link': [
                {'relation': 'self', 'url': request.url},
            ],
        }
    )


@fhir_bp.route('/Patient/<int:patient_id>', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor')
@handle_route_errors
def fhir_patient(patient_id):
    patient = _patient_or_404(patient_id)
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
        patient = _patient_or_404(patient_id)
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
                    'valueString': lr.value,
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


@fhir_bp.route('/Condition', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor')
@handle_route_errors
def fhir_conditions():
    patient_id = request.args.get('patient', type=int)
    conditions = []
    if patient_id:
        patient = _patient_or_404(patient_id)
        # Get medical records as conditions
        from models.medical_record import MedicalRecord

        records = (
            db.session.execute(select(MedicalRecord).filter_by(patient_id=patient_id).limit(50))
            .scalars()
            .all()
        )
        for rec in records:
            conditions.append(
                {
                    'resourceType': 'Condition',
                    'id': str(rec.id),
                    'clinicalStatus': {
                        'coding': [
                            {
                                'system': 'http://terminology.hl7.org/CodeSystem/condition-clinical',
                                'code': 'active',
                            }
                        ]
                    },
                    'code': {
                        'text': getattr(rec, 'diagnosis', None)
                        or getattr(rec, 'chief_complaint', 'Unknown')
                    },
                    'subject': {'reference': f'Patient/{patient_id}'},
                    'recordedDate': rec.created_at.isoformat() if rec.created_at else None,
                }
            )
    _log_fhir_access('SEARCH', 'Condition')
    return jsonify(
        {
            'resourceType': 'Bundle',
            'type': 'searchset',
            'total': len(conditions),
            'entry': [{'resource': c} for c in conditions],
        }
    )


@fhir_bp.route('/MedicationRequest', methods=['GET'])
@login_required
@role_required('admin', 'manager', 'doctor')
@handle_route_errors
def fhir_medication_requests():
    patient_id = request.args.get('patient', type=int)
    requests_list = []
    if patient_id:
        patient = _patient_or_404(patient_id)
        from models.medication import Prescription

        prescriptions = (
            db.session.execute(select(Prescription).filter_by(patient_id=patient_id).limit(50))
            .scalars()
            .all()
        )
        for rx in prescriptions:
            requests_list.append(
                {
                    'resourceType': 'MedicationRequest',
                    'id': str(rx.id),
                    'status': 'active',
                    'intent': 'order',
                    'medicationCodeableConcept': {
                        'text': (
                            rx.items.first().medication.trade_name
                            if rx.items.first() and rx.items.first().medication
                            else None
                        )
                        or getattr(rx, 'diagnosis', 'Unknown')
                    },
                    'subject': {'reference': f'Patient/{patient_id}'},
                    'authoredOn': rx.created_at.isoformat() if rx.created_at else None,
                }
            )
    _log_fhir_access('SEARCH', 'MedicationRequest')
    return jsonify(
        {
            'resourceType': 'Bundle',
            'type': 'searchset',
            'total': len(requests_list),
            'entry': [{'resource': r} for r in requests_list],
        }
    )
