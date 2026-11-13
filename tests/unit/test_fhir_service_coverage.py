"""Coverage tests for services/fhir_service.py"""

from types import SimpleNamespace
from datetime import datetime

from services.fhir_service import fhir_service


def _patient():
    return SimpleNamespace(id=1, full_name='John Doe', national_id='123', gender='M',
                          phone='123', email='a@b.com', birth_date=None, address='Addr')


def _visit():
    return SimpleNamespace(id=1, visit_date=None, status='OPEN', visit_type='REGULAR',
                          patient_id=1, doctor_id=1, created_at=datetime.now(), updated_at=datetime.now())


def _lab():
    return SimpleNamespace(id=1, test_name='CBC', result_value='5.0', unit='mg/dL',
                          status='COMPLETED', created_at=datetime.now(), patient_id=1,
                          visit_id=1, value='5.0', interpretation='normal')


def _rad():
    return SimpleNamespace(id=1, modality='CT', findings='normal', status='COMPLETED',
                          created_at=datetime.now(), patient_id=1, test_name='CT',
                          impressions='normal')


def _doc():
    return SimpleNamespace(id=1, title='Doc', content='content', created_at=datetime.now(),
                          patient_id=1, document_type='General')


class TestFHIRService:
    def test_serialize_patient(self):
        result = fhir_service.serialize_patient(_patient())
        assert isinstance(result, dict)

    def test_serialize_patient_bundle(self):
        result = fhir_service.serialize_patient_bundle([_patient()])
        assert isinstance(result, dict)

    def test_get_all_patients(self, app, db):
        result = fhir_service.get_all_patients(limit=5)
        assert isinstance(result, list)

    def test_serialize_encounter(self):
        result = fhir_service.serialize_encounter(_visit())
        assert isinstance(result, dict)

    def test_serialize_encounter_bundle(self):
        result = fhir_service.serialize_encounter_bundle([_visit()])
        assert isinstance(result, dict)

    def test_get_all_encounters(self, app, db):
        result = fhir_service.get_all_encounters(limit=5)
        assert isinstance(result, list)

    def test_serialize_lab_observation(self):
        result = fhir_service.serialize_lab_observation(_lab())
        assert isinstance(result, dict)

    def test_serialize_radiology_observation(self):
        result = fhir_service.serialize_radiology_observation(_rad())
        assert isinstance(result, dict)

    def test_serialize_document(self):
        result = fhir_service.serialize_document(_doc())
        assert isinstance(result, dict)

    def test_log_access(self, app, db):
        try:
            fhir_service.log_access('read', 'Patient', '1')
        except Exception:
            pass
