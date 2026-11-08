"""Parametrized smoke tests for the extended FHIR read API.

Every /api/fhir/* GET surface must answer a FHIR resource, not a 500/crash.
"""

from __future__ import annotations

import pytest

from tests.tenant_context import ensure_test_user, login_test_client

FHIR_GET_PATHS = [
    '/Practitioner',
    '/Organization',
    '/Appointment',
    '/AllergyIntolerance',
    '/Procedure',
    '/Immunization',
    '/DiagnosticReport',
    '/ServiceRequest',
    '/Coverage',
    '/RelatedPerson',
    '/Task',
    '/Communication',
    '/DocumentReference',
    '/CarePlan',
    '/Goal',
    '/Specimen',
    '/Device',
    '/HealthcareService',
    '/metadata',
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
    '/OperationOutcome',
]


@pytest.fixture
def fhir_client(app, client, db, test_tenant):
    user = ensure_test_user(db, test_tenant, username='fhir_extended_admin', role='admin')
    login_test_client(client, user, test_tenant, 'ValidPass123!')
    return client


@pytest.mark.parametrize('path', FHIR_GET_PATHS)
def test_fhir_get_returns_json_resource(fhir_client, path):
    resp = fhir_client.get('/api/fhir' + path)
    assert resp.status_code == 200, f'{path} -> {resp.status_code}'
    body = resp.get_json(silent=True)
    assert body is not None, f'{path} returned non-JSON'
    assert 'resourceType' in body, f'{path} body has no resourceType'


class TestAnonymousBlocked:
    @pytest.mark.parametrize('path', FHIR_GET_PATHS)
    def test_anonymous_not_200(self, client, path):
        resp = client.get('/api/fhir' + path)
        assert resp.status_code in (302, 401, 403, 404)
