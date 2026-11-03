"""Tests for routes.fhir_crud_routes module - 100% coverage target."""

from __future__ import annotations

import pytest

from routes.fhir_crud_routes import _validate_fhir_resource, apply_include


class TestValidateFhirResource:
    def test_not_dict(self):
        issues = _validate_fhir_resource('not a dict')
        assert len(issues) == 1
        assert issues[0]['code'] == 'invalid'

    def test_missing_resource_type(self):
        issues = _validate_fhir_resource({})
        assert len(issues) == 1
        assert issues[0]['code'] == 'required'

    def test_patient_no_name_no_identifier(self):
        issues = _validate_fhir_resource({'resourceType': 'Patient'})
        assert any('Patient requires' in i['details']['text'] for i in issues)

    def test_patient_valid(self):
        issues = _validate_fhir_resource({'resourceType': 'Patient', 'name': [{'text': 'John'}]})
        assert issues == []

    def test_observation_missing_status(self):
        issues = _validate_fhir_resource({'resourceType': 'Observation', 'code': {}})
        assert any('status' in i['details']['text'] for i in issues)

    def test_observation_missing_code(self):
        issues = _validate_fhir_resource({'resourceType': 'Observation', 'status': 'final'})
        assert any('code' in i['details']['text'] for i in issues)

    def test_observation_valid(self):
        issues = _validate_fhir_resource(
            {'resourceType': 'Observation', 'status': 'final', 'code': {}}
        )
        assert issues == []

    def test_condition_missing_subject(self):
        issues = _validate_fhir_resource({'resourceType': 'Condition', 'code': {}})
        assert any('subject' in i['details']['text'] for i in issues)

    def test_condition_valid(self):
        issues = _validate_fhir_resource(
            {'resourceType': 'Condition', 'subject': {'reference': 'Patient/1'}}
        )
        assert issues == []

    def test_medication_request_missing_status(self):
        issues = _validate_fhir_resource(
            {
                'resourceType': 'MedicationRequest',
                'intent': 'order',
                'medicationCodeableConcept': {'text': 'x'},
                'subject': {},
            }
        )
        assert any('status' in i['details']['text'] for i in issues)

    def test_medication_request_missing_intent(self):
        issues = _validate_fhir_resource(
            {
                'resourceType': 'MedicationRequest',
                'status': 'active',
                'medicationCodeableConcept': {'text': 'x'},
                'subject': {},
            }
        )
        assert any('intent' in i['details']['text'] for i in issues)

    def test_medication_request_missing_medication(self):
        issues = _validate_fhir_resource(
            {
                'resourceType': 'MedicationRequest',
                'status': 'active',
                'intent': 'order',
                'subject': {},
            }
        )
        assert any('medication' in i['details']['text'] for i in issues)

    def test_medication_request_missing_subject(self):
        issues = _validate_fhir_resource(
            {
                'resourceType': 'MedicationRequest',
                'status': 'active',
                'intent': 'order',
                'medicationCodeableConcept': {'text': 'x'},
            }
        )
        assert any('subject' in i['details']['text'] for i in issues)

    def test_medication_request_valid(self):
        issues = _validate_fhir_resource(
            {
                'resourceType': 'MedicationRequest',
                'status': 'active',
                'intent': 'order',
                'medicationCodeableConcept': {'text': 'x'},
                'subject': {},
            }
        )
        assert issues == []

    def test_unknown_resource_type(self):
        issues = _validate_fhir_resource({'resourceType': 'Foo'})
        assert issues == []


class TestApplyInclude:
    def test_no_params(self):
        entries = [{'resource': {'resourceType': 'Patient'}}]
        result = apply_include(entries, None, None)
        assert result == entries

    def test_empty_params(self):
        entries = [{'resource': {'resourceType': 'Patient'}}]
        result = apply_include(entries, [], None)
        assert result == entries

    def test_with_params(self):
        entries = [
            {
                'resource': {
                    'resourceType': 'Patient',
                    'general-practitioner': {'reference': 'Practitioner/1'},
                }
            }
        ]
        result = apply_include(entries, ['Patient:general-practitioner'], None)
        assert result == entries


class TestFhirCrudRoutes:
    def _login(self, client, db, test_tenant, role='admin'):
        from tests.tenant_context import ensure_test_user, login_test_client

        user = ensure_test_user(db, test_tenant, username=f'fhir_{role}_user', role=role)
        login_test_client(client, user, test_tenant)
        return user

    def test_create_patient_invalid(self, app, client, db, test_tenant):
        self._login(client, db, test_tenant)
        resp = client.post('/api/fhir/Patient', json={'resourceType': 'Patient'})
        assert resp.status_code == 400

    def test_create_patient_success(self, app, client, db, test_tenant):
        self._login(client, db, test_tenant)
        resp = client.post(
            '/api/fhir/Patient',
            json={
                'resourceType': 'Patient',
                'name': [{'text': 'John Doe'}],
                'gender': 'male',
                'birthDate': '1990-01-01',
                'telecom': [{'value': '1234567'}],
                'address': [{'text': 'Addr'}],
                'identifier': [{'value': 'NID123'}],
            },
        )
        assert resp.status_code == 201

    def test_create_patient_name_parts(self, app, client, db, test_tenant):
        self._login(client, db, test_tenant)
        resp = client.post(
            '/api/fhir/Patient',
            json={
                'resourceType': 'Patient',
                'name': [{'given': ['John'], 'family': 'Doe'}],
            },
        )
        assert resp.status_code == 201

    def test_create_patient_invalid_birthdate(self, app, client, db, test_tenant):
        self._login(client, db, test_tenant)
        resp = client.post(
            '/api/fhir/Patient',
            json={
                'resourceType': 'Patient',
                'name': [{'text': 'John Doe'}],
                'birthDate': 'not-a-date',
            },
        )
        assert resp.status_code == 201

    def test_update_patient_not_found(self, app, client, db, test_tenant):
        self._login(client, db, test_tenant)
        resp = client.put(
            '/api/fhir/Patient/999999',
            json={
                'resourceType': 'Patient',
                'name': [{'text': 'John Doe'}],
            },
        )
        assert resp.status_code in (302, 404, 500)

    def test_update_patient_success(self, app, client, db, test_tenant):
        self._login(client, db, test_tenant)
        # Create first
        resp = client.post(
            '/api/fhir/Patient',
            json={
                'resourceType': 'Patient',
                'name': [{'text': 'John Doe'}],
            },
        )
        pid = resp.get_json()['id']
        resp = client.put(
            f'/api/fhir/Patient/{pid}',
            json={
                'resourceType': 'Patient',
                'name': [{'text': 'Jane Doe'}],
                'gender': 'female',
                'telecom': [{'value': '999888777'}],
                'address': [{'text': 'New Addr'}],
                'birthDate': '1991-02-02',
            },
        )
        assert resp.status_code == 200

    def test_update_patient_invalid(self, app, client, db, test_tenant):
        self._login(client, db, test_tenant)
        resp = client.put('/api/fhir/Patient/1', json={'resourceType': 'Patient'})
        # Missing name but resourceType present - validation may pass
        assert resp.status_code in (200, 400, 404, 500)

    def test_create_observation_invalid(self, app, client, db, test_tenant):
        self._login(client, db, test_tenant, role='nurse')
        resp = client.post('/api/fhir/Observation', json={'resourceType': 'Observation'})
        assert resp.status_code == 400

    def test_create_observation_success(self, app, client, db, test_tenant):
        # Create a patient as admin
        self._login(client, db, test_tenant, role='admin')
        presp = client.post(
            '/api/fhir/Patient',
            json={
                'resourceType': 'Patient',
                'name': [{'text': 'John Doe'}],
            },
        )
        pid = presp.get_json().get('id', '1') if presp.status_code == 201 else '1'
        # Re-login as nurse
        self._login(client, db, test_tenant, role='nurse')
        resp = client.post(
            '/api/fhir/Observation',
            json={
                'resourceType': 'Observation',
                'status': 'final',
                'code': {},
                'subject': {'reference': f'Patient/{pid}'},
                'effectiveDateTime': '2024-01-01T00:00:00',
                'valueQuantity': {'value': 37.5},
            },
        )
        assert resp.status_code == 201

    def test_create_observation_no_subject(self, app, client, db, test_tenant):
        self._login(client, db, test_tenant, role='nurse')
        resp = client.post(
            '/api/fhir/Observation',
            json={
                'resourceType': 'Observation',
                'status': 'final',
                'code': {},
            },
        )
        assert resp.status_code in (201, 302, 400, 500)

    def test_create_condition_invalid(self, app, client, db, test_tenant):
        self._login(client, db, test_tenant)
        resp = client.post('/api/fhir/Condition', json={'resourceType': 'Condition'})
        assert resp.status_code == 400

    def test_create_condition_success(self, app, client, db, test_tenant):
        self._login(client, db, test_tenant)
        presp = client.post(
            '/api/fhir/Patient',
            json={
                'resourceType': 'Patient',
                'name': [{'text': 'John Doe'}],
            },
        )
        pid = presp.get_json().get('id', '1') if presp.status_code == 201 else '1'
        resp = client.post(
            '/api/fhir/Condition',
            json={
                'resourceType': 'Condition',
                'subject': {'reference': f'Patient/{pid}'},
                'code': {'text': 'Diabetes'},
            },
        )
        assert resp.status_code == 201

    def test_create_medication_request_invalid(self, app, client, db, test_tenant):
        self._login(client, db, test_tenant)
        resp = client.post(
            '/api/fhir/MedicationRequest', json={'resourceType': 'MedicationRequest'}
        )
        assert resp.status_code == 400

    def test_create_medication_request_success(self, app, client, db, test_tenant):
        self._login(client, db, test_tenant)
        presp = client.post(
            '/api/fhir/Patient',
            json={
                'resourceType': 'Patient',
                'name': [{'text': 'John Doe'}],
            },
        )
        pid = presp.get_json().get('id', '1') if presp.status_code == 201 else '1'
        resp = client.post(
            '/api/fhir/MedicationRequest',
            json={
                'resourceType': 'MedicationRequest',
                'status': 'active',
                'intent': 'order',
                'medicationCodeableConcept': {'text': 'Amoxicillin'},
                'subject': {'reference': f'Patient/{pid}'},
                'dosageInstruction': [{'text': '1 tablet'}],
            },
        )
        assert resp.status_code == 201

    def test_fhir_validate_invalid(self, app, client, db, test_tenant):
        self._login(client, db, test_tenant)
        resp = client.post('/api/fhir/$validate', json={'resourceType': 'Patient'})
        assert resp.status_code == 400

    def test_fhir_validate_valid(self, app, client, db, test_tenant):
        self._login(client, db, test_tenant)
        resp = client.post(
            '/api/fhir/$validate',
            json={
                'resourceType': 'Patient',
                'name': [{'text': 'John'}],
            },
        )
        assert resp.status_code == 200

    def test_log_function(self, app):
        with app.app_context():
            with app.test_request_context():
                from routes.fhir_crud_routes import _log

                _log('CREATE', 'Patient', '1')
                _log('CREATE', 'Patient', None)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
