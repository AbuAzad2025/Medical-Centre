"""HTTP tests for routes.fhir_api_routes (HL7 FHIR API)."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from models.patient import Patient
from tests.tenant_context import ensure_test_user, login_test_client


@pytest.fixture
def fhir_client(app, client, db, test_tenant):
    user = ensure_test_user(db, test_tenant, username='fhir_doctor', role='doctor')
    login_test_client(client, user, test_tenant, 'ValidPass123!')
    return client


@pytest.fixture
def patient_info(app, db, test_tenant):
    suffix = datetime.now(UTC).strftime('%H%M%S%f')
    p = Patient(
        tenant_id=test_tenant.id,
        first_name=f'Fhir{suffix}',
        last_name='Patient',
        phone=f'0523{suffix[-6:]}',
        gender='F',
        birth_date=date(1990, 5, 1),
    )
    db.session.add(p)
    db.session.commit()
    return p, suffix


@pytest.fixture
def patient(patient_info):
    return patient_info[0]


class TestPatientSearch:
    def test_patient_search_by_name(self, fhir_client, patient_info):
        patient, suffix = patient_info
        resp = fhir_client.get(f'/api/fhir/Patient?name=Fhir{suffix}')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['resourceType'] == 'Bundle'
        assert body['total'] >= 1
        assert any(int(e['resource']['id']) == patient.id for e in body['entry'])

    def test_patient_search_name_not_returned_when_nothing_matches(self, fhir_client, patient):
        resp = fhir_client.get(f'/api/fhir/Patient?name=definitely-no-match-xyz-{patient.id}')
        assert resp.status_code == 200
        assert all(int(e['resource']['id']) != patient.id for e in resp.get_json()['entry'])

    def test_patient_search_gender(self, fhir_client, patient):
        resp = fhir_client.get('/api/fhir/Patient?gender=F')
        assert resp.status_code == 200
        assert resp.get_json()['resourceType'] == 'Bundle'

    def test_patient_search_birthdate(self, fhir_client, patient):
        resp = fhir_client.get('/api/fhir/Patient?birthdate=1990-05-01')
        assert resp.status_code == 200

    def test_patient_read(self, fhir_client, patient):
        resp = fhir_client.get(f'/api/fhir/Patient/{patient.id}')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['resourceType'] == 'Patient'
        assert body['id'] == str(patient.id)

    def test_patient_read_missing_returns_404(self, fhir_client):
        resp = fhir_client.get('/api/fhir/Patient/999999')
        assert resp.status_code == 404

    def test_patient_search_sort(self, fhir_client, patient_info):
        _patient, suffix = patient_info
        resp = fhir_client.get(f'/api/fhir/Patient?name=Fhir{suffix}&_sort=birth_date')
        assert resp.status_code == 200

    def test_patient_search_count_offset(self, fhir_client, patient_info):
        _patient, suffix = patient_info
        resp = fhir_client.get(f'/api/fhir/Patient?name=Fhir{suffix}&_count=5&_offset=0')
        assert resp.status_code == 200

    def test_patient_search_count_abuse(self, fhir_client, patient_info):
        _patient, suffix = patient_info
        resp = fhir_client.get(f'/api/fhir/Patient?name=Fhir{suffix}&_count=99999')
        assert resp.status_code == 200


class TestOtherResources:
    def test_encounter_list(self, fhir_client, patient):
        resp = fhir_client.get('/api/fhir/Encounter')
        assert resp.status_code == 200
        assert resp.get_json()['resourceType'] == 'Bundle'

    def test_observation_missing_patient_404(self, fhir_client):
        resp = fhir_client.get('/api/fhir/Observation?patient=999999')
        assert resp.status_code == 404

    def test_observation_for_patient(self, fhir_client, patient):
        resp = fhir_client.get(f'/api/fhir/Observation?patient={patient.id}')
        assert resp.status_code == 200
        assert resp.get_json()['resourceType'] == 'Bundle'

    def test_condition_missing_patient_404(self, fhir_client):
        resp = fhir_client.get('/api/fhir/Condition?patient=999999')
        assert resp.status_code == 404

    def test_condition_for_patient(self, fhir_client, patient):
        resp = fhir_client.get(f'/api/fhir/Condition?patient={patient.id}')
        assert resp.status_code == 200
        assert resp.get_json()['resourceType'] == 'Bundle'

    def test_medication_request_missing_patient_404(self, fhir_client):
        resp = fhir_client.get('/api/fhir/MedicationRequest?patient=999999')
        assert resp.status_code == 404

    def test_medication_request_for_patient(self, fhir_client, patient):
        resp = fhir_client.get(f'/api/fhir/MedicationRequest?patient={patient.id}')
        assert resp.status_code == 200
        assert resp.get_json()['resourceType'] == 'Bundle'


class TestAnonymous:
    def test_anonymous_redirected(self, client):
        resp = client.get('/api/fhir/Patient')
        assert resp.status_code in (302, 401, 403, 404)
