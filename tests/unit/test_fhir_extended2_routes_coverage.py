"""HTTP coverage tests for routes/fhir_extended2_routes.py (fhir_bp3).

Every test drives the Flask test client against ``/api/fhir/...`` — the same
blueprint the app registers in app_factory.py. Rows are created inside each
test and rolled back by ``rollback_db`` (pulled in via ``test_tenant``).

Known-bug sentinels are marked as such and assert the *current* behaviour;
they should start failing once the route is fixed. Bugs found are reported in
docs/reports notes for this mission.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from tests.tenant_context import ensure_test_user, login_test_client

FHIR = '/api/fhir'

BUNDLE_GET_PATHS = [
    '/Medication',
    '/MedicationAdministration',
    '/MedicationDispense',
    '/MedicationStatement',
    '/Location',
    '/NutritionOrder',
    '/VisionPrescription',
    '/Invoice',
    '/Claim',
    '/ChargeItem',
    '/Flag',
    '/List',
    '/Provenance',
    '/AuditEvent',
    '/Consent',
    '/ResearchStudy',
    '/Endpoint',
    '/Substance',
    '/BodyStructure',
    '/Questionnaire',
    '/QuestionnaireResponse',
    '/Group',
    '/Schedule',
]


@pytest.fixture
def fhir_admin(app, client, db, test_tenant):
    """Log in an admin user against the rolled-back test tenant."""
    user = ensure_test_user(db, test_tenant, username='fhir2_cov_admin', role='admin')
    login_test_client(client, user, test_tenant, 'ValidPass123!')
    return SimpleNamespace(client=client, user=user, tenant=test_tenant)


def _save(db, obj):
    db.session.add(obj)
    db.session.commit()
    return obj


def _patient(db, tenant_id, **kwargs):
    from models.patient import Patient

    patient = Patient(
        tenant_id=tenant_id,
        first_name='Coverage',
        last_name=f'Patient{uuid4().hex[:8]}',
        gender='M',
        **kwargs,
    )
    return _save(db, patient)


def _medication(db, tenant_id, **kwargs):
    from models.medication import Medication

    suffix = uuid4().hex[:8]
    med = Medication(
        tenant_id=tenant_id,
        trade_name=f'CovTrade{suffix}',
        scientific_name=f'CovSci{suffix}',
        dosage_form='tablet',
        strength='500mg',
        price=10,
        **kwargs,
    )
    return _save(db, med)


# ---------------------------------------------------------------------------
# Smoke: every GET endpoint answers a FHIR resource over HTTP.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize('path', BUNDLE_GET_PATHS)
def test_get_endpoints_return_bundle(fhir_admin, path):
    resp = fhir_admin.client.get(FHIR + path)
    assert resp.status_code == 200, f'{path} -> {resp.status_code}'
    body = resp.get_json()
    assert body['resourceType'] == 'Bundle'
    assert body['type'] == 'searchset'


def test_operation_outcome_get(fhir_admin):
    resp = fhir_admin.client.get(f'{FHIR}/OperationOutcome')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['resourceType'] == 'OperationOutcome'
    assert body['issue'][0]['code'] == 'informational'


# ---------------------------------------------------------------------------
# POST /Medication — validation branches (_validate_resource/_operation_outcome)
# ---------------------------------------------------------------------------


def test_post_medication_rejects_non_object_json(fhir_admin):
    resp = fhir_admin.client.post(f'{FHIR}/Medication', json=[1, 2, 3])
    assert resp.status_code == 400
    body = resp.get_json()
    assert body['resourceType'] == 'OperationOutcome'
    assert any(i['code'] == 'invalid' for i in body['issue'])


def test_post_medication_rejects_missing_resource_type(fhir_admin):
    resp = fhir_admin.client.post(f'{FHIR}/Medication', json={})
    assert resp.status_code == 400
    body = resp.get_json()
    assert body['resourceType'] == 'OperationOutcome'
    assert any(i['code'] == 'required' for i in body['issue'])


def test_post_medication_currently_broken(fhir_admin):
    """Sentinel for the known bug in the POST branch.

    ``Medication(name=...)`` sets the read-only ``name`` property, so SQLAlchemy's
    default constructor raises AttributeError and the request never reaches the
    201 path. Expected once fixed: 201 with resourceType 'Medication'.
    """
    resp = fhir_admin.client.post(
        f'{FHIR}/Medication',
        json={'resourceType': 'Medication', 'code': {'text': 'SentinelMed'}},
        headers={'Accept': 'application/json'},
    )
    assert resp.status_code == 500
    assert resp.get_json()['success'] is False


def test_post_medication_success_path(fhir_admin, monkeypatch):
    """Green path for the 201 branch.

    The route's ``Medication(name=...)`` call is broken (read-only property), so
    the class-level ``name`` property is removed for this test only; the HTTP
    request, validation, commit and response rendering all run for real.
    """
    from models.medication import Medication

    monkeypatch.delattr(Medication, 'name')
    resp = fhir_admin.client.post(
        f'{FHIR}/Medication',
        json={'resourceType': 'Medication', 'code': {'text': 'CoverageMed'}},
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body['resourceType'] == 'Medication'
    assert body['code']['text'] == 'CoverageMed'


# ---------------------------------------------------------------------------
# MedicationAdministration / MedicationDispense / MedicationStatement
# ---------------------------------------------------------------------------


def test_medication_administration_with_rows(fhir_admin, db):
    from models.emar import eMARAdministration

    patient = _patient(db, fhir_admin.tenant.id)
    med = _medication(db, fhir_admin.tenant.id)
    record = eMARAdministration(
        tenant_id=fhir_admin.tenant.id,
        patient_id=patient.id,
        medication_id=med.id,
        scheduled_time=datetime.now(UTC),
        status='GIVEN',
    )
    _save(db, record)

    resp = fhir_admin.client.get(f'{FHIR}/MedicationAdministration')
    assert resp.status_code == 200
    ids = [e['resource']['id'] for e in resp.get_json()['entry']]
    assert str(record.id) in ids

    resp = fhir_admin.client.get(f'{FHIR}/MedicationAdministration?patient={patient.id}')
    assert resp.status_code == 200
    entries = resp.get_json()['entry']
    assert any(e['resource']['id'] == str(record.id) for e in entries)
    admin_entry = next(e['resource'] for e in entries if e['resource']['id'] == str(record.id))
    assert admin_entry['status'] == 'given'
    assert admin_entry['medicationCodeableConcept']['text'] == med.trade_name
    assert admin_entry['subject']['reference'] == f'Patient/{patient.id}'

    resp = fhir_admin.client.get(f'{FHIR}/MedicationAdministration?patient=999999')
    assert resp.status_code == 200
    assert resp.get_json()['entry'] == []


def test_medication_dispense_with_rows(fhir_admin, db):
    from models.medication import Prescription, PrescriptionDispenseLog

    patient = _patient(db, fhir_admin.tenant.id)
    prescription = Prescription(
        tenant_id=fhir_admin.tenant.id,
        patient_id=patient.id,
        prescription_number=f'RX{uuid4().hex[:10]}',
    )
    _save(db, prescription)
    dispense = PrescriptionDispenseLog(
        tenant_id=fhir_admin.tenant.id,
        prescription_id=prescription.id,
        patient_id=patient.id,
        dispensed_at=datetime.now(UTC),
    )
    _save(db, dispense)

    resp = fhir_admin.client.get(f'{FHIR}/MedicationDispense')
    assert resp.status_code == 200
    assert any(e['resource']['id'] == str(dispense.id) for e in resp.get_json()['entry'])

    resp = fhir_admin.client.get(f'{FHIR}/MedicationDispense?patient={patient.id}')
    assert resp.status_code == 200
    entries = resp.get_json()['entry']
    assert any(e['resource']['id'] == str(dispense.id) for e in entries)
    entry = next(e['resource'] for e in entries if e['resource']['id'] == str(dispense.id))
    assert entry['status'] == 'completed'
    assert entry['subject']['reference'] == f'Patient/{patient.id}'
    assert entry['whenHandedOver'] is not None


def test_medication_statement_with_rows(fhir_admin, db):
    from models.medication_reconciliation import MedicationReconciliation

    patient = _patient(db, fhir_admin.tenant.id)
    reconciliation = MedicationReconciliation(
        tenant_id=fhir_admin.tenant.id,
        patient_id=patient.id,
        transition_type='ADMISSION',
        status='PENDING',
    )
    _save(db, reconciliation)

    resp = fhir_admin.client.get(f'{FHIR}/MedicationStatement')
    assert resp.status_code == 200
    assert any(e['resource']['id'] == str(reconciliation.id) for e in resp.get_json()['entry'])

    resp = fhir_admin.client.get(f'{FHIR}/MedicationStatement?patient={patient.id}')
    assert resp.status_code == 200
    entries = resp.get_json()['entry']
    assert any(e['resource']['id'] == str(reconciliation.id) for e in entries)
    entry = next(e['resource'] for e in entries if e['resource']['id'] == str(reconciliation.id))
    assert entry['status'] == 'pending'
    assert entry['subject']['reference'] == f'Patient/{patient.id}'


# ---------------------------------------------------------------------------
# Location
# ---------------------------------------------------------------------------


def test_location_with_bed(fhir_admin, db):
    from models.bed_management import Bed, Room, Ward

    suffix = uuid4().hex[:8]
    ward = _save(
        db, Ward(tenant_id=fhir_admin.tenant.id, name=f'CovWard{suffix}', code=f'W{suffix}')
    )
    room = _save(
        db,
        Room(tenant_id=fhir_admin.tenant.id, ward_id=ward.id, name=f'R{suffix}', code=f'R{suffix}'),
    )
    bed = _save(
        db,
        Bed(tenant_id=fhir_admin.tenant.id, room_id=room.id, bed_number=f'B{suffix}'),
    )

    resp = fhir_admin.client.get(f'{FHIR}/Location')
    assert resp.status_code == 200
    entries = resp.get_json()['entry']
    assert any(e['resource']['id'] == str(bed.id) for e in entries)
    entry = next(e['resource'] for e in entries if e['resource']['id'] == str(bed.id))
    assert entry['name'] == bed.bed_number
    assert entry['mode'] == 'instance'


# ---------------------------------------------------------------------------
# Invoice / Claim
# ---------------------------------------------------------------------------


def _invoice(db, tenant_id, **kwargs):
    from models.invoice import Invoice

    invoice = Invoice(
        tenant_id=tenant_id,
        status='ISSUED',
        total_amount=123.45,
        **kwargs,
    )
    return _save(db, invoice)


def test_invoice_with_rows(fhir_admin, db):
    invoice = _invoice(db, fhir_admin.tenant.id)

    resp = fhir_admin.client.get(f'{FHIR}/Invoice')
    assert resp.status_code == 200
    entries = resp.get_json()['entry']
    assert any(e['resource']['id'] == str(invoice.id) for e in entries)
    entry = next(e['resource'] for e in entries if e['resource']['id'] == str(invoice.id))
    assert entry['status'] == 'issued'
    assert entry['totalNet'] == {'value': 123.45, 'currency': 'USD'}


def test_invoice_patient_filter_currently_broken(fhir_admin, db):
    """Sentinel for the known bug in the patient filter branch.

    ``Invoice`` has no ``patient_id`` column, so ``Invoice.patient_id`` raises
    AttributeError. Expected once fixed: a filtered Bundle.
    """
    _invoice(db, fhir_admin.tenant.id)
    resp = fhir_admin.client.get(
        f'{FHIR}/Invoice?patient=1', headers={'Accept': 'application/json'}
    )
    assert resp.status_code == 500


def test_claim_with_rows(fhir_admin, db):
    invoice = _invoice(db, fhir_admin.tenant.id)

    resp = fhir_admin.client.get(f'{FHIR}/Claim')
    assert resp.status_code == 200
    entries = resp.get_json()['entry']
    assert any(e['resource']['id'] == str(invoice.id) for e in entries)
    entry = next(e['resource'] for e in entries if e['resource']['id'] == str(invoice.id))
    assert entry['type']['text'] == 'professional'


def test_claim_patient_filter_currently_broken(fhir_admin, db):
    """Sentinel for the same Invoice.patient_id bug in the Claim route."""
    _invoice(db, fhir_admin.tenant.id)
    resp = fhir_admin.client.get(f'{FHIR}/Claim?patient=1', headers={'Accept': 'application/json'})
    assert resp.status_code == 500


def test_charge_item_with_rows(fhir_admin, db):
    from models.service import ServiceMaster

    suffix = uuid4().hex[:8]
    service = _save(
        db,
        ServiceMaster(
            tenant_id=fhir_admin.tenant.id,
            code=f'SVC{suffix}',
            name=f'CovService{suffix}',
            base_price=77.5,
        ),
    )

    resp = fhir_admin.client.get(f'{FHIR}/ChargeItem')
    assert resp.status_code == 200
    entries = resp.get_json()['entry']
    assert any(e['resource']['id'] == str(service.id) for e in entries)
    entry = next(e['resource'] for e in entries if e['resource']['id'] == str(service.id))
    assert entry['code']['text'] == service.name
    assert entry['priceOverride']['value'] == 77.5


# ---------------------------------------------------------------------------
# Flag / List
# ---------------------------------------------------------------------------


def test_flag_with_rows(fhir_admin, db):
    patient = _patient(db, fhir_admin.tenant.id)

    resp = fhir_admin.client.get(f'{FHIR}/Flag')
    assert resp.status_code == 200
    assert any(e['resource']['id'] == str(patient.id) for e in resp.get_json()['entry'])

    resp = fhir_admin.client.get(f'{FHIR}/Flag?patient={patient.id}')
    assert resp.status_code == 200
    entries = resp.get_json()['entry']
    assert any(e['resource']['id'] == str(patient.id) for e in entries)
    entry = next(e['resource'] for e in entries if e['resource']['id'] == str(patient.id))
    assert entry['subject']['reference'] == f'Patient/{patient.id}'


def test_list_with_rows(fhir_admin, db):
    from models.problem_list import PatientProblem

    patient = _patient(db, fhir_admin.tenant.id)
    problem = _save(
        db,
        PatientProblem(
            tenant_id=fhir_admin.tenant.id,
            patient_id=patient.id,
            problem_description='Coverage hypertension',
        ),
    )

    resp = fhir_admin.client.get(f'{FHIR}/List')
    assert resp.status_code == 200
    assert any(e['resource']['id'] == str(problem.id) for e in resp.get_json()['entry'])

    resp = fhir_admin.client.get(f'{FHIR}/List?patient={patient.id}')
    assert resp.status_code == 200
    entries = resp.get_json()['entry']
    assert any(e['resource']['id'] == str(problem.id) for e in entries)
    entry = next(e['resource'] for e in entries if e['resource']['id'] == str(problem.id))
    assert entry['title'] == 'Coverage hypertension'


# ---------------------------------------------------------------------------
# Provenance / AuditEvent
# ---------------------------------------------------------------------------


def test_provenance_with_rows(fhir_admin, db):
    from models.audit_trail import AuditTrail

    audit = _save(
        db,
        AuditTrail(
            tenant_id=fhir_admin.tenant.id,
            entity_type='patient',
            entity_id=1,
            action='view',
            user_id=fhir_admin.user.id,
        ),
    )

    resp = fhir_admin.client.get(f'{FHIR}/Provenance')
    assert resp.status_code == 200
    entries = resp.get_json()['entry']
    assert any(e['resource']['id'] == str(audit.id) for e in entries)
    entry = next(e['resource'] for e in entries if e['resource']['id'] == str(audit.id))
    assert entry['target'] == [{'reference': 'patient/1'}]
    assert entry['activity'] == {'text': 'view'}


def test_audit_event_with_rows(fhir_admin, db):
    from models.phi_audit_log import PHIAuditLog

    log = _save(
        db,
        PHIAuditLog(
            tenant_id=fhir_admin.tenant.id,
            actor_id=fhir_admin.user.id,
            target_model='Patient',
            target_id=1,
            action='CREATE',
        ),
    )

    resp = fhir_admin.client.get(f'{FHIR}/AuditEvent')
    assert resp.status_code == 200
    entries = resp.get_json()['entry']
    assert any(e['resource']['id'] == str(log.id) for e in entries)
    entry = next(e['resource'] for e in entries if e['resource']['id'] == str(log.id))
    assert entry['type'] == {'text': 'CREATE'}


# ---------------------------------------------------------------------------
# Consent
# ---------------------------------------------------------------------------


def test_consent_with_rows(fhir_admin, db):
    from models.consent_management import PatientConsent

    patient = _patient(db, fhir_admin.tenant.id)
    consent = _save(
        db,
        PatientConsent(
            tenant_id=fhir_admin.tenant.id,
            patient_id=patient.id,
            consent_type='treatment',
            scope_description='Coverage test consent',
            status='granted',
            recorded_by_user_id=fhir_admin.user.id,
        ),
    )

    resp = fhir_admin.client.get(f'{FHIR}/Consent')
    assert resp.status_code == 200
    assert any(e['resource']['id'] == str(consent.id) for e in resp.get_json()['entry'])

    resp = fhir_admin.client.get(f'{FHIR}/Consent?patient={patient.id}')
    assert resp.status_code == 200
    entries = resp.get_json()['entry']
    assert any(e['resource']['id'] == str(consent.id) for e in entries)
    entry = next(e['resource'] for e in entries if e['resource']['id'] == str(consent.id))
    assert entry['status'] == 'granted'
    assert entry['scope']['text'] == 'treatment'
    assert entry['patient']['reference'] == f'Patient/{patient.id}'


# ---------------------------------------------------------------------------
# Endpoint / Substance / Questionnaire / QuestionnaireResponse
# ---------------------------------------------------------------------------


def test_endpoint_with_rows(fhir_admin, db):
    from models.sso_config import SSOConfiguration

    suffix = uuid4().hex[:8]
    config = _save(
        db,
        SSOConfiguration(
            tenant_id=fhir_admin.tenant.id,
            provider_type='ldap',
            name=f'CovLDAP{suffix}',
            is_active=True,
        ),
    )

    resp = fhir_admin.client.get(f'{FHIR}/Endpoint')
    assert resp.status_code == 200
    entries = resp.get_json()['entry']
    assert any(e['resource']['id'] == str(config.id) for e in entries)
    entry = next(e['resource'] for e in entries if e['resource']['id'] == str(config.id))
    assert entry['connectionType'] == {'code': 'hl7-fhir-rest'}


def test_substance_with_rows(fhir_admin, db):
    med = _medication(db, fhir_admin.tenant.id)

    resp = fhir_admin.client.get(f'{FHIR}/Substance')
    assert resp.status_code == 200
    entries = resp.get_json()['entry']
    assert any(e['resource']['id'] == str(med.id) for e in entries)
    entry = next(e['resource'] for e in entries if e['resource']['id'] == str(med.id))
    assert entry['code']['text'] == med.trade_name


def test_questionnaire_with_rows(fhir_admin, db):
    from models.specialty_form import SpecialtyForm

    suffix = uuid4().hex[:8]
    form = _save(
        db,
        SpecialtyForm(
            tenant_id=fhir_admin.tenant.id,
            name=f'CovForm{suffix}',
            slug=f'cov-form-{suffix}',
        ),
    )

    resp = fhir_admin.client.get(f'{FHIR}/Questionnaire')
    assert resp.status_code == 200
    entries = resp.get_json()['entry']
    assert any(e['resource']['id'] == str(form.id) for e in entries)
    entry = next(e['resource'] for e in entries if e['resource']['id'] == str(form.id))
    assert entry['title'] == form.name


def test_questionnaire_response_with_rows(fhir_admin, db):
    from models.specialty_form import SpecialtyForm, SpecialtyFormSubmission, SpecialtyFormVersion

    patient = _patient(db, fhir_admin.tenant.id)
    suffix = uuid4().hex[:8]
    form = _save(
        db,
        SpecialtyForm(
            tenant_id=fhir_admin.tenant.id,
            name=f'CovForm{suffix}',
            slug=f'cov-form-{suffix}',
        ),
    )
    version = _save(
        db,
        SpecialtyFormVersion(
            tenant_id=fhir_admin.tenant.id,
            form_id=form.id,
            version_number=1,
            status='published',
        ),
    )
    submission = _save(
        db,
        SpecialtyFormSubmission(
            tenant_id=fhir_admin.tenant.id,
            version_id=version.id,
            patient_id=patient.id,
            answers={'q1': 'a1'},
        ),
    )

    resp = fhir_admin.client.get(f'{FHIR}/QuestionnaireResponse')
    assert resp.status_code == 200
    entries = resp.get_json()['entry']
    assert any(e['resource']['id'] == str(submission.id) for e in entries)
    entry = next(e['resource'] for e in entries if e['resource']['id'] == str(submission.id))
    assert entry['status'] == 'completed'
    assert entry['subject']['reference'] == f'Patient/{patient.id}'


# ---------------------------------------------------------------------------
# Group / Schedule
# ---------------------------------------------------------------------------


def test_group_with_patients(fhir_admin, db):
    _patient(db, fhir_admin.tenant.id)
    _patient(db, fhir_admin.tenant.id)

    resp = fhir_admin.client.get(f'{FHIR}/Group')
    assert resp.status_code == 200
    entries = resp.get_json()['entry']
    assert entries, 'expected at least one Group entry'
    unassigned = [e['resource'] for e in entries if e['resource']['id'] == 'unassigned']
    assert unassigned, 'expected an unassigned Group entry'
    group = unassigned[0]
    assert group['type'] == 'person'
    assert group['actual'] is True
    assert group['quantity'] == len(group['member'])
    assert group['member'], 'expected group members'


def test_schedule_with_appointments(fhir_admin, db):
    from models.appointment import Appointment

    patient = _patient(db, fhir_admin.tenant.id)
    starts = datetime.now(UTC) + timedelta(days=1)
    appointment = _save(
        db,
        Appointment(
            tenant_id=fhir_admin.tenant.id,
            patient_id=patient.id,
            doctor_id=fhir_admin.user.id,
            starts_at=starts,
            ends_at=starts + timedelta(hours=1),
            status='SCHEDULED',
        ),
    )

    resp = fhir_admin.client.get(f'{FHIR}/Schedule')
    assert resp.status_code == 200
    entries = resp.get_json()['entry']
    mine = [e['resource'] for e in entries if e['resource']['id'] == str(fhir_admin.user.id)]
    assert mine, 'expected a Schedule grouped under the doctor'
    schedule = mine[0]
    assert schedule['active'] is True
    assert schedule['actor'] == [{'reference': f'Practitioner/{fhir_admin.user.id}'}]
    assert schedule['planningHorizon']['start'] == appointment.starts_at.isoformat()
    assert schedule['planningHorizon']['end'] == appointment.ends_at.isoformat()


# ---------------------------------------------------------------------------
# _log failure is swallowed and the request still succeeds
# ---------------------------------------------------------------------------


def test_audit_log_failure_does_not_break_request(fhir_admin, monkeypatch):
    from models import fhir_mapping

    def boom(*_args, **_kwargs):
        raise RuntimeError('fhir audit store unavailable')

    monkeypatch.setattr(fhir_mapping, 'FHIRAuditLog', boom)

    resp = fhir_admin.client.get(f'{FHIR}/NutritionOrder')
    assert resp.status_code == 200
    assert resp.get_json()['resourceType'] == 'Bundle'


# ---------------------------------------------------------------------------
# /metadata is shadowed by fhir_extended_routes (registered first), so the
# fhir_ext2 copy of the handler can only be exercised directly.
# ---------------------------------------------------------------------------


def test_metadata_route_served_over_http(fhir_admin):
    resp = fhir_admin.client.get(f'{FHIR}/metadata')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['resourceType'] == 'CapabilityStatement'


def test_metadata_handler_direct_call(app):
    from routes.fhir_extended2_routes import fhir_metadata

    with app.test_request_context(f'{FHIR}/metadata'):
        response = fhir_metadata.__wrapped__()
    body = response.get_json()
    assert body['resourceType'] == 'CapabilityStatement'
    assert body['fhirVersion'] == '4.0.1'
    assert body['rest'][0]['resource'], 'expected resource list'
    types = {r['type'] for r in body['rest'][0]['resource']}
    assert {'Medication', 'Schedule', 'OperationOutcome'} <= types
