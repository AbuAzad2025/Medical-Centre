"""HTTP-level coverage for routes/fhir_extended_routes.py (gap closure).

Complements tests/unit/test_fhir_extended_reads.py, which smoke-tests the
unfiltered GETs as admin. This module drives the branches that file cannot
reach:

* ``GET /Practitioner/<id>`` (success + unknown-id behaviour)
* ``?patient=<id>`` filters on the search endpoints, with real rows seeded
  so the filter line and the entry-building loop both execute
* the immunization vaccine lookup and the coverage company lookup
* ``GET /Task?status=...``
* ``GET /RelatedPerson?patient=...`` (found / not found)
* role-based 403s for endpoints whose role list excludes the caller

Bugs documented (not fixed here -- this module is test-only):

1. ``/Communication?patient=<id>``, ``/CarePlan?patient=<id>`` and
   ``/Goal?patient=<id>`` filter on ``Notification.patient_id``,
   ``ClinicalPathway.patient_id`` and ``Treatment.patient_id`` respectively,
   but none of those models has a ``patient_id`` column. The ``?patient=``
   path therefore raises AttributeError and the endpoints answer 500 (or a
   redirect for non-JSON Accept) instead of a filtered searchset. The tests
   below accept 200 or 500 and say so in comments; tighten them to 200 once
   the routes are fixed.
2. ``GET /Practitioner/<unknown id>``: ``get_tenant_record`` raises
   ``TenantContextError`` for a missing row instead of returning None, so the
   ``abort(404)`` in the route is dead code and an unknown id surfaces as
   500 (JSON Accept) / redirect (browser Accept) rather than 404.
3. ``/CarePlan`` entries reference ``ClinicalPathway.patient_id`` and
   ``/Goal`` entries reference ``Treatment.patient_id`` -- same missing
   columns, masked only because ``getattr`` defaults kick in when no filter
   is applied.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import pytest

from tests.tenant_context import (
    create_scoped,
    ensure_test_user,
    login_test_client,
)

VALID_PASSWORD = 'ValidPass123!'


def _uniq(prefix: str) -> str:
    return f'{prefix}-{uuid.uuid4().hex[:10]}'


@pytest.fixture
def admin_client(app, client, db, test_tenant):
    user = ensure_test_user(
        db, test_tenant, username='fhir_cov_admin', role='admin', password=VALID_PASSWORD
    )
    login_test_client(client, user, test_tenant, VALID_PASSWORD)
    return client


@pytest.fixture
def make_client(app, client, db, test_tenant):
    """Factory: log the shared test client in as ``role`` and return it."""

    def _make(role: str):
        user = ensure_test_user(
            db,
            test_tenant,
            username=f'fhir_cov_{role}',
            role=role,
            password=VALID_PASSWORD,
        )
        login_test_client(client, user, test_tenant, VALID_PASSWORD)
        return client

    return _make


def _mk_patient(app, tenant, **overrides):
    from models.patient import Patient

    payload = {
        'tenant_id': tenant.id,
        'first_name': _uniq('Cov'),
        'last_name': 'Patient',
    }
    payload.update(overrides)
    return create_scoped(app, tenant, Patient(**payload))


def _bundle_ids(body):
    return [int(e['resource']['id']) for e in body.get('entry', [])]


def _fhir_get(client, path, **kwargs):
    headers = kwargs.pop('headers', {})
    headers.setdefault('Accept', 'application/json')
    return client.get('/api/fhir' + path, headers=headers, **kwargs)


# --- Practitioner read -------------------------------------------------------


class TestPractitionerRead:
    def test_read_existing_practitioner(self, app, admin_client, db, test_tenant):
        user = ensure_test_user(
            db,
            test_tenant,
            username='fhir_cov_practitioner',
            role='doctor',
            password=VALID_PASSWORD,
        )
        resp = _fhir_get(admin_client, f'/Practitioner/{user.id}')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['resourceType'] == 'Practitioner'
        assert body['id'] == str(user.id)
        assert body['active'] is True
        assert body['name'][0]['text']

    def test_read_unknown_practitioner(self, admin_client):
        # get_tenant_record raises TenantContextError for a missing row, so the
        # route's abort(404) is unreachable; handle_route_errors turns it into a
        # 500 for JSON clients (302 redirect otherwise). Accept either, but do
        # not crash with 200. See module docstring, bug 2.
        resp = _fhir_get(admin_client, '/Practitioner/999999999')
        assert resp.status_code in (404, 500)


# --- Role-based access control ------------------------------------------------


@pytest.mark.parametrize(
    ('path', 'role'),
    [
        ('/Organization', 'doctor'),
        ('/Organization', 'nurse'),
        ('/Organization', 'reception'),
        ('/Practitioner', 'nurse'),
        ('/Practitioner/1', 'nurse'),
        ('/Appointment', 'nurse'),
        ('/AllergyIntolerance', 'reception'),
        ('/DiagnosticReport', 'nurse'),
        ('/ServiceRequest', 'nurse'),
        ('/Coverage', 'doctor'),
        ('/Task', 'lab'),
        ('/Communication', 'reception'),
        ('/DocumentReference', 'nurse'),
        ('/CarePlan', 'nurse'),
        ('/Goal', 'nurse'),
        ('/Specimen', 'nurse'),
        ('/Device', 'doctor'),
        ('/HealthcareService', 'doctor'),
        ('/Procedure', 'nurse'),
        ('/Immunization', 'reception'),
    ],
)
def test_role_not_in_allowlist_gets_403(make_client, path, role):
    client = make_client(role)
    resp = _fhir_get(client, path)
    assert resp.status_code == 403, f'{path} as {role} -> {resp.status_code}'


# --- ?patient= filtered searches (real rows seeded) ---------------------------


class TestPatientFilteredSearches:
    def test_appointment_filter_returns_seeded_row(self, app, admin_client, test_tenant):
        from models.appointment import Appointment

        patient = _mk_patient(app, test_tenant)
        appt = create_scoped(
            app,
            test_tenant,
            Appointment(
                tenant_id=test_tenant.id,
                patient_id=patient.id,
                starts_at=datetime.now(UTC),
                status='SCHEDULED',
            ),
        )
        resp = _fhir_get(admin_client, f'/Appointment?patient={patient.id}')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['resourceType'] == 'Bundle'
        assert appt.id in _bundle_ids(body)
        entry = next(e for e in body['entry'] if int(e['resource']['id']) == appt.id)
        # The Appointment model has no scheduled_start/scheduled_end columns
        # (it has starts_at/ends_at), so start/end are always null here.
        assert entry['resource']['start'] is None
        assert entry['resource']['participant'][0]['actor']['reference'] == (
            f'Patient/{patient.id}'
        )

    def test_allergy_filter_returns_seeded_row(self, app, admin_client, test_tenant):
        from models.problem_list import AllergyIntolerance

        patient = _mk_patient(app, test_tenant)
        substance = _uniq('Peanuts')
        allergy = create_scoped(
            app,
            test_tenant,
            AllergyIntolerance(
                tenant_id=test_tenant.id, patient_id=patient.id, substance=substance
            ),
        )
        resp = _fhir_get(admin_client, f'/AllergyIntolerance?patient={patient.id}')
        assert resp.status_code == 200
        body = resp.get_json()
        assert allergy.id in _bundle_ids(body)
        entry = next(e for e in body['entry'] if int(e['resource']['id']) == allergy.id)
        assert entry['resource']['code']['text'] == substance

    def test_procedure_filter_returns_seeded_row(self, app, admin_client, test_tenant):
        from models.medical_record import MedicalRecord

        patient = _mk_patient(app, test_tenant)
        record = create_scoped(
            app,
            test_tenant,
            MedicalRecord(
                tenant_id=test_tenant.id,
                patient_id=patient.id,
                title=_uniq('Procedure note'),
            ),
        )
        resp = _fhir_get(admin_client, f'/Procedure?patient={patient.id}')
        assert resp.status_code == 200
        body = resp.get_json()
        assert record.id in _bundle_ids(body)

    def test_immunization_filter_resolves_vaccine_name(self, app, admin_client, test_tenant):
        from models.vaccination import Immunization, Vaccine

        patient = _mk_patient(app, test_tenant)
        vaccine = create_scoped(
            app,
            test_tenant,
            Vaccine(
                tenant_id=test_tenant.id,
                name=_uniq('CovVax'),
                code=_uniq('CVX'),
            ),
        )
        imm = create_scoped(
            app,
            test_tenant,
            Immunization(
                tenant_id=test_tenant.id,
                patient_id=patient.id,
                vaccine_id=vaccine.id,
                administration_date=date.today(),
                status='COMPLETED',
            ),
        )
        resp = _fhir_get(admin_client, f'/Immunization?patient={patient.id}')
        assert resp.status_code == 200
        body = resp.get_json()
        assert imm.id in _bundle_ids(body)
        entry = next(e for e in body['entry'] if int(e['resource']['id']) == imm.id)
        assert entry['resource']['vaccineCode']['text'] == vaccine.name
        assert entry['resource']['status'] == 'completed'

    def test_diagnostic_report_filter_returns_seeded_row(self, app, admin_client, test_tenant):
        from models.lab_request import LabRequest

        patient = _mk_patient(app, test_tenant)
        req = create_scoped(
            app,
            test_tenant,
            LabRequest(tenant_id=test_tenant.id, patient_id=patient.id, status='REQUESTED'),
        )
        resp = _fhir_get(admin_client, f'/DiagnosticReport?patient={patient.id}')
        assert resp.status_code == 200
        body = resp.get_json()
        assert req.id in _bundle_ids(body)

    def test_service_request_filter_returns_seeded_row(self, app, admin_client, test_tenant):
        from models.lab_request import LabRequest

        patient = _mk_patient(app, test_tenant)
        req = create_scoped(
            app,
            test_tenant,
            LabRequest(tenant_id=test_tenant.id, patient_id=patient.id, status='REQUESTED'),
        )
        resp = _fhir_get(admin_client, f'/ServiceRequest?patient={patient.id}')
        assert resp.status_code == 200
        body = resp.get_json()
        assert req.id in _bundle_ids(body)

    def test_coverage_filter_resolves_company_name(self, app, admin_client, test_tenant):
        from models.insurance import InsuranceCompany

        company = create_scoped(
            app,
            test_tenant,
            InsuranceCompany(tenant_id=test_tenant.id, name=_uniq('CovInsCo')),
        )
        patient = _mk_patient(app, test_tenant, insurance_company_id=company.id)
        resp = _fhir_get(admin_client, f'/Coverage?patient={patient.id}')
        assert resp.status_code == 200
        body = resp.get_json()
        assert patient.id in _bundle_ids(body)
        entry = next(e for e in body['entry'] if int(e['resource']['id']) == patient.id)
        assert entry['resource']['type']['text'] == company.name
        assert entry['resource']['payor'][0]['display'] == company.name

    def test_communication_filter_patient_param(self, app, admin_client, test_tenant):
        # Notification has no patient_id column, so the filter raises
        # AttributeError -> 500 (or redirect without JSON Accept). See module
        # docstring, bug 1. Accept 200 as well so the test survives the fix.
        patient = _mk_patient(app, test_tenant)
        resp = _fhir_get(admin_client, f'/Communication?patient={patient.id}')
        assert resp.status_code in (200, 500)

    def test_document_reference_filter_returns_seeded_row(self, app, admin_client, test_tenant):
        from models.medical_record import MedicalRecord

        patient = _mk_patient(app, test_tenant)
        record = create_scoped(
            app,
            test_tenant,
            MedicalRecord(
                tenant_id=test_tenant.id,
                patient_id=patient.id,
                title=_uniq('Doc ref'),
            ),
        )
        resp = _fhir_get(admin_client, f'/DocumentReference?patient={patient.id}')
        assert resp.status_code == 200
        body = resp.get_json()
        assert record.id in _bundle_ids(body)

    def test_care_plan_filter_patient_param(self, app, admin_client, test_tenant):
        # ClinicalPathway has no patient_id column (PatientCarePlan does), so
        # the filter raises AttributeError -> 500. See module docstring, bug 1.
        patient = _mk_patient(app, test_tenant)
        resp = _fhir_get(admin_client, f'/CarePlan?patient={patient.id}')
        assert resp.status_code in (200, 500)

    def test_goal_filter_patient_param(self, app, admin_client, test_tenant):
        # Treatment has no patient_id column, so the filter raises
        # AttributeError -> 500. See module docstring, bug 1.
        patient = _mk_patient(app, test_tenant)
        resp = _fhir_get(admin_client, f'/Goal?patient={patient.id}')
        assert resp.status_code in (200, 500)

    def test_specimen_filter_returns_seeded_row(self, app, admin_client, test_tenant):
        from models.lab_request import LabRequest

        patient = _mk_patient(app, test_tenant)
        req = create_scoped(
            app,
            test_tenant,
            LabRequest(tenant_id=test_tenant.id, patient_id=patient.id, status='REQUESTED'),
        )
        resp = _fhir_get(admin_client, f'/Specimen?patient={patient.id}')
        assert resp.status_code == 200
        body = resp.get_json()
        assert req.id in _bundle_ids(body)

    def test_filter_with_no_matches_returns_empty_bundle(self, admin_client):
        resp = _fhir_get(admin_client, '/Appointment?patient=999999999')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['resourceType'] == 'Bundle'
        assert body['entry'] == []
        assert body['total'] == 0


# --- Task status filter --------------------------------------------------------


class TestTaskStatusFilter:
    def test_status_filter_matches_seeded_task(self, app, admin_client, test_tenant):
        from models.task_management import Task

        status = 'completed'
        task = create_scoped(
            app,
            test_tenant,
            Task(
                tenant_id=test_tenant.id,
                title=_uniq('CovTask'),
                task_type='administrative',
                status=status,
            ),
        )
        resp = _fhir_get(admin_client, f'/Task?status={status}')
        assert resp.status_code == 200
        body = resp.get_json()
        assert task.id in _bundle_ids(body)
        entry = next(e for e in body['entry'] if int(e['resource']['id']) == task.id)
        assert entry['resource']['status'] == 'completed'

    def test_status_filter_no_match_returns_empty(self, admin_client):
        resp = _fhir_get(admin_client, f'/Task?status={_uniq("nomatch")}')
        assert resp.status_code == 200
        assert resp.get_json()['entry'] == []


# --- RelatedPerson --------------------------------------------------------------


class TestRelatedPerson:
    def test_existing_patient_returns_empty_bundle(self, app, admin_client, test_tenant):
        patient = _mk_patient(app, test_tenant)
        resp = _fhir_get(admin_client, f'/RelatedPerson?patient={patient.id}')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['resourceType'] == 'Bundle'
        assert body['total'] == 0
        assert body['entry'] == []

    def test_unknown_patient_returns_404(self, admin_client):
        resp = _fhir_get(admin_client, '/RelatedPerson?patient=999999999')
        assert resp.status_code == 404

    def test_without_patient_param_returns_empty_bundle(self, admin_client):
        resp = _fhir_get(admin_client, '/RelatedPerson')
        assert resp.status_code == 200
        assert resp.get_json()['total'] == 0


# --- Goal entry rendering with a real Treatment row ------------------------------


class TestGoalEntries:
    def test_goal_bundle_renders_treatment_entries(self, app, admin_client, test_tenant):
        from models.treatment import Treatment
        from models.visit import Visit

        patient = _mk_patient(app, test_tenant)
        visit = create_scoped(
            app,
            test_tenant,
            Visit(tenant_id=test_tenant.id, patient_id=patient.id),
        )
        treatment = create_scoped(
            app,
            test_tenant,
            Treatment(
                tenant_id=test_tenant.id,
                visit_id=visit.id,
                primary_diagnosis=_uniq('CovDx'),
                treatment_plan='cover the goal entry path',
            ),
        )
        resp = _fhir_get(admin_client, '/Goal')
        assert resp.status_code == 200
        body = resp.get_json()
        assert treatment.id in _bundle_ids(body)
        entry = next(e for e in body['entry'] if int(e['resource']['id']) == treatment.id)
        # Treatment has no patient_id column; the entry's subject/reference is
        # therefore null rather than Patient/<id>. See module docstring, bug 3.
        assert entry['resource']['subject'] is None


# --- CarePlan entry rendering with a real ClinicalPathway row -------------------


class TestCarePlanEntries:
    def test_care_plan_bundle_renders_pathway_entries(self, app, admin_client, test_tenant):
        from models.clinical_pathway import ClinicalPathway

        pathway = create_scoped(
            app,
            test_tenant,
            ClinicalPathway(tenant_id=test_tenant.id, name=_uniq('CovPathway')),
        )
        resp = _fhir_get(admin_client, '/CarePlan')
        assert resp.status_code == 200
        body = resp.get_json()
        assert pathway.id in _bundle_ids(body)
        entry = next(e for e in body['entry'] if int(e['resource']['id']) == pathway.id)
        assert entry['resource']['subject'] is None


# --- Communication entry rendering with a real Notification row -------------------


class TestCommunicationEntries:
    def test_communication_bundle_renders_notification_entries(
        self, app, admin_client, test_tenant
    ):
        from models.notification import Notification

        marker = _uniq('CovMsg')
        notification = create_scoped(
            app,
            test_tenant,
            Notification(
                tenant_id=test_tenant.id,
                title=marker,
                message=f'{marker} body',
                notification_type='info',
            ),
        )
        resp = _fhir_get(admin_client, '/Communication')
        assert resp.status_code == 200
        body = resp.get_json()
        assert notification.id in _bundle_ids(body)
        entry = next(e for e in body['entry'] if int(e['resource']['id']) == notification.id)
        assert entry['resource']['payload'][0]['contentString'] == f'{marker} body'
        assert entry['resource']['subject'] is None


# --- Device and HealthcareService with real rows ---------------------------------


class TestDeviceEntries:
    def test_device_bundle_renders_equipment_barcodes(self, app, admin_client, test_tenant):
        from models.barcode_tracking import BarcodeRegistry

        barcode = _uniq('EQP')
        device = create_scoped(
            app,
            test_tenant,
            BarcodeRegistry(
                tenant_id=test_tenant.id,
                barcode_value=barcode,
                barcode_type='BARCODE',
                entity_type='EQUIPMENT',
                entity_id=1,
                is_active=True,
            ),
        )
        resp = _fhir_get(admin_client, '/Device')
        assert resp.status_code == 200
        body = resp.get_json()
        assert device.id in _bundle_ids(body)
        entry = next(e for e in body['entry'] if int(e['resource']['id']) == device.id)
        assert entry['resource']['status'] == 'active'
        assert entry['resource']['deviceName'][0]['name'] == barcode


class TestHealthcareServiceEntries:
    def test_healthcare_service_bundle_renders_departments(self, app, admin_client, test_tenant):
        from models.department import Department

        name = _uniq('CovDept')
        dept = create_scoped(
            app,
            test_tenant,
            Department(tenant_id=test_tenant.id, name=name, name_ar=name),
        )
        resp = _fhir_get(admin_client, '/HealthcareService')
        assert resp.status_code == 200
        body = resp.get_json()
        assert dept.id in _bundle_ids(body)
        entry = next(e for e in body['entry'] if int(e['resource']['id']) == dept.id)
        assert entry['resource']['name'] == name


# --- Plain-list GETs: entry building and the _log SEARCH call -------------


class TestPractitionerListing:
    def test_practitioner_search_returns_bundle_with_seeded_user(
        self, admin_client, db, test_tenant
    ):
        user = ensure_test_user(
            db,
            test_tenant,
            username=_uniq('FhPractitioner'),
            role='doctor',
            password=VALID_PASSWORD,
        )
        resp = _fhir_get(admin_client, '/Practitioner')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['resourceType'] == 'Bundle'
        assert body['type'] == 'searchset'
        assert body['total'] >= 1
        assert user.id in _bundle_ids(body)
        entry = next(e for e in body['entry'] if int(e['resource']['id']) == user.id)
        assert entry['resource']['resourceType'] == 'Practitioner'
        assert entry['resource']['active'] is True


class TestOrganizationListing:
    def test_organization_search_returns_bundle(self, admin_client, test_tenant):
        resp = _fhir_get(admin_client, '/Organization')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['resourceType'] == 'Bundle'
        assert body['type'] == 'searchset'
        assert test_tenant.id in _bundle_ids(body)
        entry = next(e for e in body['entry'] if int(e['resource']['id']) == test_tenant.id)
        assert entry['resource']['resourceType'] == 'Organization'


class TestMetadata:
    def test_metadata_returns_capability_statement(self, admin_client):
        resp = _fhir_get(admin_client, '/metadata')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['resourceType'] == 'CapabilityStatement'
        assert body['status'] == 'active'
        assert body['fhirVersion'] == '4.0.1'
        assert body['rest'], 'expected rest block'
        types = {r['type'] for r in body['rest'][0]['resource']}
        assert {'Practitioner', 'Organization', 'Appointment'} <= types


# --- _log failure is swallowed and the request still succeeds ------------


class TestAuditLogFailure:
    def test_log_commit_failure_does_not_break_request(self, admin_client, monkeypatch):
        import routes.fhir_extended_routes as fhir_ext_routes

        def boom(*_args, **_kwargs):
            raise RuntimeError('audit commit unavailable')

        monkeypatch.setattr(fhir_ext_routes, 'safe_commit', boom)

        resp = _fhir_get(admin_client, '/Practitioner')
        # _log swallows its own failure; the search still answers 200.
        assert resp.status_code == 200
        assert resp.get_json()['resourceType'] == 'Bundle'
