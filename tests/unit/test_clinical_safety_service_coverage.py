"""Coverage tests for services/clinical_safety_service.py"""

from unittest.mock import patch, MagicMock


class TestClinicalSafetyService:
    def test_check_allergies_no_context(self):
        from services.clinical_safety_service import ClinicalSafetyService
        result = ClinicalSafetyService._check_allergies(999999, [], 999999)
        assert isinstance(result, list)

    def test_check_drug_interactions_no_context(self):
        from services.clinical_safety_service import ClinicalSafetyService
        result = ClinicalSafetyService._check_drug_interactions(999999, [], 999999)
        assert isinstance(result, list)

    def test_check_contraindications_no_context(self):
        from services.clinical_safety_service import ClinicalSafetyService
        result = ClinicalSafetyService._check_contraindications(999999, [], 999999)
        assert isinstance(result, list)

    def test_check_pregnancy_safety_no_context(self):
        from services.clinical_safety_service import ClinicalSafetyService
        result = ClinicalSafetyService._check_pregnancy_safety(999999, [], 999999)
        assert isinstance(result, list)

    def test_check_duplicate_therapy_no_context(self):
        from services.clinical_safety_service import ClinicalSafetyService
        result = ClinicalSafetyService._check_duplicate_therapy(999999, [], 999999)
        assert isinstance(result, list)

    def test_check_prescription_safety_no_context(self):
        from services.clinical_safety_service import ClinicalSafetyService
        ok, alerts = ClinicalSafetyService.check_prescription_safety(999999, 999999, [], 999999, 999999)
        assert isinstance(ok, bool)
        assert isinstance(alerts, list)