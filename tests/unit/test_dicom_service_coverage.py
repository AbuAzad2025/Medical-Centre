"""Coverage tests for services/dicom_service.py"""

from services.dicom_service import dicom_service


class TestDICOMService:
    def test_get_studies(self, app, db, test_tenant):
        result = dicom_service.get_studies()
        assert isinstance(result, list)

    def test_get_studies_with_patient(self, app, db, test_tenant):
        result = dicom_service.get_studies(patient_id=1)
        assert isinstance(result, list)

    def test_get_studies_with_modality(self, app, db, test_tenant):
        result = dicom_service.get_studies(modality='CT')
        assert isinstance(result, list)

    def test_get_series(self, app, db, test_tenant):
        result = dicom_service.get_series(999999)
        assert isinstance(result, list)

    def test_get_instances(self, app, db, test_tenant):
        result = dicom_service.get_instances(999999)
        assert isinstance(result, list)

    def test_get_patient_studies(self, app, db, test_tenant):
        result = dicom_service.get_patient_studies(999999)
        assert isinstance(result, list)

    def test_get_pacs_config(self, app, db, test_tenant):
        result = dicom_service.get_pacs_config()
        assert isinstance(result, list)

    def test_serialize_study(self, app, db, test_tenant):
        from types import SimpleNamespace
        study = SimpleNamespace(
            id=1, modality='CT', status='ACTIVE', study_date=None,
            study_instance_uid='uid', study_description='desc', series_count=2,
        )
        result = dicom_service.serialize_study(study)
        assert isinstance(result, dict)
        assert result['id'] == 1
