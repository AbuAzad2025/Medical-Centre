"""Extended HTTP tests for routes.fhir_api_routes (HL7 FHIR API).

Covers the branches the base suite (tests/unit/test_fhir_api_routes.py) leaves
uncovered: _include/_revinclude handling, the name-search sort/pagination
fallbacks, audit-log failure handling, the defensive ``patient is None``
branch, and the Observation/Condition/MedicationRequest bodies once the
patient actually has data.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from models.lab_request import LabRequest, LabResult
from models.medical_record import MedicalRecord
from models.medication import Medication, Prescription, PrescriptionItem
from models.patient import Patient
from models.visit import Visit
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


@pytest.fixture
def clinical_rows(app, db, test_tenant, patient):
    """One lab result and one medical record for ``patient``."""
    request = LabRequest(tenant_id=test_tenant.id, patient_id=patient.id)
    db.session.add(request)
    db.session.flush()
    lab_result = LabResult(
        tenant_id=test_tenant.id,
        request_id=request.id,
        patient_id=patient.id,
        test_code='GLU',
        test_name='Glucose',
        value='5.4',
    )
    record = MedicalRecord(
        tenant_id=test_tenant.id,
        patient_id=patient.id,
        title='Annual checkup',
        diagnosis='Routine review',
    )
    db.session.add_all([lab_result, record])
    db.session.commit()
    return lab_result, record


@pytest.fixture
def prescriptions(app, db, test_tenant, patient):
    """Three prescriptions for ``patient``: with item, without item but with
    diagnosis, and without item nor diagnosis."""
    suffix = datetime.now(UTC).strftime('%H%M%S%f')
    medication = Medication(
        tenant_id=test_tenant.id,
        scientific_name=f'Scientia{suffix}',
        trade_name=f'Trade{suffix}',
        dosage_form='tablet',
        strength='500mg',
        price=Decimal('2.5'),
    )
    rx_with_item = Prescription(
        tenant_id=test_tenant.id,
        patient_id=patient.id,
        prescription_number=f'RX-{suffix}-A',
        diagnosis='Migraine',
    )
    rx_no_item_diag = Prescription(
        tenant_id=test_tenant.id,
        patient_id=patient.id,
        prescription_number=f'RX-{suffix}-B',
        diagnosis='Flu',
    )
    rx_no_item_no_diag = Prescription(
        tenant_id=test_tenant.id,
        patient_id=patient.id,
        prescription_number=f'RX-{suffix}-C',
        diagnosis=None,
    )
    db.session.add_all([medication, rx_with_item, rx_no_item_diag, rx_no_item_no_diag])
    db.session.commit()
    item = PrescriptionItem(
        tenant_id=test_tenant.id,
        prescription_id=rx_with_item.id,
        medication_id=medication.id,
        dosage='1 tablet daily',
        quantity=1,
        unit_price=Decimal('2.5'),
        total_price=Decimal('2.5'),
    )
    db.session.add(item)
    db.session.commit()
    return {
        'medication': medication,
        'with_item': rx_with_item,
        'no_item_diag': rx_no_item_diag,
        'no_item_no_diag': rx_no_item_no_diag,
    }


class TestPatientOr404:
    def test_get_tenant_record_returning_none_yields_404(self, fhir_client, monkeypatch):
        monkeypatch.setattr('routes.fhir_api_routes.get_tenant_record', lambda *_a, **_k: None)
        resp = fhir_client.get('/api/fhir/Patient/1')
        assert resp.status_code == 404


class TestAuditLogFailure:
    def test_audit_log_failure_still_returns_200(self, fhir_client, monkeypatch):
        def _boom(*args, **kwargs):
            raise RuntimeError('audit write failed')

        monkeypatch.setattr('routes.fhir_api_routes.safe_commit', _boom)
        resp = fhir_client.get('/api/fhir/Patient')
        assert resp.status_code == 200


class TestPatientNameSearchFallbacks:
    def test_name_search_invalid_count_and_offset_fall_back_to_defaults(
        self, fhir_client, patient_info
    ):
        _patient, suffix = patient_info
        resp = fhir_client.get(f'/api/fhir/Patient?name=Fhir{suffix}&_count=abc&_offset=xyz')
        assert resp.status_code == 200
        assert any(e['resource']['id'] == str(_patient.id) for e in resp.get_json()['entry'])

    def test_name_search_sort_descending(self, fhir_client, patient_info):
        _patient, suffix = patient_info
        resp = fhir_client.get(f'/api/fhir/Patient?name=Fhir{suffix}&_sort=-birth_date')
        assert resp.status_code == 200

    def test_name_search_sort_with_unstringable_value(self, fhir_client, patient_info, monkeypatch):
        _patient, suffix = patient_info

        class ExplodingStr:
            def __str__(self):
                raise ValueError('cannot stringify')

        monkeypatch.setattr(
            Patient, 'boom_sort_field', property(lambda _self: ExplodingStr()), raising=False
        )
        resp = fhir_client.get(f'/api/fhir/Patient?name=Fhir{suffix}&_sort=boom_sort_field')
        assert resp.status_code == 200


class TestPatientInclude:
    def test_include_general_practitioner_adds_practitioner_entries(
        self, fhir_client, patient_info, db, test_tenant, monkeypatch
    ):
        _patient, suffix = patient_info
        doctor = ensure_test_user(db, test_tenant, username='fhir_doctor', role='doctor')
        monkeypatch.setattr(Patient, 'doctor_id', doctor.id, raising=False)
        resp = fhir_client.get(
            f'/api/fhir/Patient?name=Fhir{suffix}'
            '&_include=Patient:general-practitioner&_include=Patient:generalPractitioner'
        )
        assert resp.status_code == 200
        entries = resp.get_json()['entry']
        practitioners = [e for e in entries if e['resource']['resourceType'] == 'Practitioner']
        assert practitioners
        assert any(e['resource']['id'] == str(doctor.id) for e in practitioners)
        assert all(e['search']['mode'] == 'include' for e in practitioners)

    def test_include_with_unknown_doctor_omits_practitioner_entries(
        self, fhir_client, patient_info, monkeypatch
    ):
        _patient, suffix = patient_info
        monkeypatch.setattr(Patient, 'doctor_id', 999999999, raising=False)
        resp = fhir_client.get(
            f'/api/fhir/Patient?name=Fhir{suffix}&_include=Patient:general-practitioner'
        )
        assert resp.status_code == 200
        entries = resp.get_json()['entry']
        assert not [e for e in entries if e['resource']['resourceType'] == 'Practitioner']


class TestPatientRevInclude:
    def test_revinclude_adds_observation_and_condition_entries(
        self, fhir_client, patient_info, clinical_rows
    ):
        _patient, suffix = patient_info
        lab_result, record = clinical_rows
        resp = fhir_client.get(
            f'/api/fhir/Patient?name=Fhir{suffix}'
            '&_revinclude=Observation:patient&_revinclude=Condition:patient'
        )
        assert resp.status_code == 200
        entries = resp.get_json()['entry']
        observations = [e for e in entries if e['resource']['resourceType'] == 'Observation']
        conditions = [e for e in entries if e['resource']['resourceType'] == 'Condition']
        assert any(e['resource']['id'] == f'lab-{lab_result.id}' for e in observations)
        assert any(e['resource']['id'] == str(record.id) for e in conditions)
        assert all(e['search']['mode'] == 'include' for e in observations + conditions)

    def test_revinclude_with_no_matching_patients_yields_empty_bundle(self, fhir_client):
        resp = fhir_client.get(
            '/api/fhir/Patient?name=definitely-no-match-xyz'
            '&_revinclude=Observation:patient&_revinclude=Condition:patient'
        )
        assert resp.status_code == 200
        assert resp.get_json()['entry'] == []


class TestEncounterWithData:
    def test_encounter_entry_references_patient(self, fhir_client, patient, db, test_tenant):
        visit = Visit(
            tenant_id=test_tenant.id,
            patient_id=patient.id,
            status='OPEN',
            visit_type='REGULAR',
        )
        db.session.add(visit)
        db.session.commit()
        resp = fhir_client.get('/api/fhir/Encounter')
        assert resp.status_code == 200
        entries = resp.get_json()['entry']
        match = [
            e for e in entries if e['resource']['subject']['reference'] == f'Patient/{patient.id}'
        ]
        assert match
        assert match[0]['resource']['status'] == 'open'
        assert match[0]['resource']['class']['code'] == 'regular'

    def test_encounter_with_null_status_and_visit_type(self, fhir_client, patient, db, test_tenant):
        from sqlalchemy import text as _text

        visit = Visit(
            tenant_id=test_tenant.id,
            patient_id=patient.id,
            status='OPEN',
            visit_type='REGULAR',
        )
        db.session.add(visit)
        db.session.commit()
        # The columns are nullable; the Python-side defaults fire at insert time,
        # so clear them with SQL to exercise the route's fallback rendering.
        db.session.execute(
            _text('UPDATE visits SET status = NULL, visit_type = NULL WHERE id = :id'),
            {'id': visit.id},
        )
        db.session.commit()
        db.session.expire_all()
        resp = fhir_client.get('/api/fhir/Encounter')
        assert resp.status_code == 200
        entries = resp.get_json()['entry']
        match = [
            e for e in entries if e['resource']['subject']['reference'] == f'Patient/{patient.id}'
        ]
        assert match
        assert match[0]['resource']['status'] == 'unknown'
        assert match[0]['resource']['class']['code'] == 'amb'


class TestObservationWithData:
    def test_observation_includes_lab_results(self, fhir_client, patient, clinical_rows):
        lab_result, _record = clinical_rows
        resp = fhir_client.get(f'/api/fhir/Observation?patient={patient.id}')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['total'] >= 1
        match = [e for e in body['entry'] if e['resource']['id'] == f'lab-{lab_result.id}']
        assert match
        resource = match[0]['resource']
        assert resource['resourceType'] == 'Observation'
        assert resource['status'] == 'final'
        assert resource['category'][0]['coding'][0]['code'] == 'laboratory'
        assert resource['code']['text'] == 'Glucose'
        assert resource['valueString'] == '5.4'


class TestConditionWithData:
    def test_condition_includes_medical_records(self, fhir_client, patient, clinical_rows):
        _lab_result, record = clinical_rows
        resp = fhir_client.get(f'/api/fhir/Condition?patient={patient.id}')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['total'] >= 1
        match = [e for e in body['entry'] if e['resource']['id'] == str(record.id)]
        assert match
        resource = match[0]['resource']
        assert resource['resourceType'] == 'Condition'
        assert resource['code']['text'] == 'Routine review'
        assert resource['subject']['reference'] == f'Patient/{patient.id}'
        assert resource['clinicalStatus']['coding'][0]['code'] == 'active'

    def test_condition_falls_back_to_unknown_without_diagnosis(
        self, fhir_client, patient, db, test_tenant
    ):
        record = MedicalRecord(
            tenant_id=test_tenant.id,
            patient_id=patient.id,
            title='Triage note',
            diagnosis=None,
        )
        db.session.add(record)
        db.session.commit()
        resp = fhir_client.get(f'/api/fhir/Condition?patient={patient.id}')
        assert resp.status_code == 200
        match = [e for e in resp.get_json()['entry'] if e['resource']['id'] == str(record.id)]
        assert match
        assert match[0]['resource']['code']['text'] == 'Unknown'


class TestMedicationRequestWithData:
    def test_medication_request_uses_item_medication_name(
        self, fhir_client, patient, prescriptions
    ):
        medication = prescriptions['medication']
        resp = fhir_client.get(f'/api/fhir/MedicationRequest?patient={patient.id}')
        assert resp.status_code == 200
        texts = [
            e['resource']['medicationCodeableConcept']['text'] for e in resp.get_json()['entry']
        ]
        assert medication.trade_name in texts

    def test_medication_request_falls_back_to_diagnosis(self, fhir_client, patient, prescriptions):
        resp = fhir_client.get(f'/api/fhir/MedicationRequest?patient={patient.id}')
        assert resp.status_code == 200
        entries = resp.get_json()['entry']
        texts = [e['resource']['medicationCodeableConcept']['text'] for e in entries]
        assert 'Flu' in texts
        # BUG (reported, not fixed): the route does
        # `getattr(rx, 'diagnosis', 'Unknown')`, but Prescription HAS a
        # `diagnosis` column, so the 'Unknown' default never applies and a
        # prescription without items and without diagnosis renders text=None.
        assert None in texts
        for entry in entries:
            assert entry['resource']['status'] == 'active'
            assert entry['resource']['intent'] == 'order'
            assert entry['resource']['subject']['reference'] == f'Patient/{patient.id}'


class TestAnonymousAccess:
    @pytest.mark.parametrize(
        'path',
        [
            '/api/fhir/Patient/1',
            '/api/fhir/Encounter',
            '/api/fhir/Observation',
            '/api/fhir/Condition',
            '/api/fhir/MedicationRequest',
        ],
    )
    def test_anonymous_redirected_or_denied(self, client, path):
        resp = client.get(path)
        assert resp.status_code in (302, 401, 403, 404)
