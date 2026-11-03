"""Tests for services.clinical_context_service module - 100% coverage target."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from services.clinical_context_service import ClinicalContextService
from utils.tenant_query import TenantContextError


class TestClinicalContextService:
    """Tests for ClinicalContextService class."""

    def test_get_visit_context_tenant_error(self):
        """Test get_visit_context returns empty dict on tenant error."""
        with patch('services.clinical_context_service.get_tenant_record') as mock_get:
            mock_get.side_effect = TenantContextError("No tenant context")

            result = ClinicalContextService.get_visit_context(1)

            assert result == {}

    def test_get_visit_context_success(self):
        """Test get_visit_context with valid visit."""
        mock_visit = MagicMock()
        mock_visit.id = 1
        mock_visit.patient_id = 1
        mock_visit.status = 'active'
        mock_visit.to_dict.return_value = {'id': 1, 'status': 'active'}

        mock_patient = MagicMock()
        mock_patient.id = 1
        mock_patient.full_name = 'John Doe'
        mock_patient.to_dict.return_value = {'id': 1, 'name': 'John Doe'}

        mock_vital = MagicMock()
        mock_vital.blood_pressure_systolic = 120
        mock_vital.blood_pressure_diastolic = 80
        mock_vital.heart_rate = 72
        mock_vital.temperature = 37.0
        mock_vital.respiratory_rate = 16
        mock_vital.oxygen_saturation = 98
        mock_vital.recorded_at = '2024-01-01'

        mock_allergy = MagicMock()
        mock_allergy.allergen = 'Penicillin'
        mock_allergy.severity = 'high'

        mock_lab = MagicMock()
        mock_lab.id = 1
        mock_lab.test_name = 'CBC'
        mock_lab.status = 'pending'

        mock_rad = MagicMock()
        mock_rad.id = 1
        mock_rad.test_name = 'X-Ray'
        mock_rad.status = 'pending'

        mock_prescription = MagicMock()
        mock_prescription.id = 1
        mock_prescription.status = 'active'

        mock_diagnosis = MagicMock()
        mock_diagnosis.icd_code = MagicMock()
        mock_diagnosis.icd_code.code = 'J06.9'
        mock_diagnosis.icd_code.description = 'Upper respiratory infection'
        mock_diagnosis.diagnosis_type = 'primary'

        with patch('services.clinical_context_service.get_tenant_record') as mock_get:
            mock_get.side_effect = [mock_visit, mock_patient]

            with patch('services.clinical_context_service.db.session.execute') as mock_execute:
                mock_result = MagicMock()
                mock_result.scalars.return_value.all.side_effect = [
                    [mock_vital],  # vitals
                    [mock_allergy],  # allergies
                    [mock_lab],  # lab_reqs
                    [mock_rad],  # rad_reqs
                    [mock_prescription],  # prescriptions
                    [mock_diagnosis],  # diagnoses
                ]
                mock_execute.return_value = mock_result

                result = ClinicalContextService.get_visit_context(1)

                assert result is not None
                assert 'visit' in result
                assert 'patient' in result
                assert 'vitals' in result
                assert 'allergies' in result
                assert 'diagnoses' in result
                assert 'lab_requests' in result
                assert 'radiology_requests' in result
                assert 'prescriptions' in result

    def test_get_timeline_empty(self):
        """Test get_timeline with no events."""
        with patch('services.clinical_context_service.db.session.execute') as mock_execute:
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_execute.return_value = mock_result

            result = ClinicalContextService.get_timeline(1)

            assert result == []

    def test_get_timeline_with_events(self):
        """Test get_timeline with events."""
        mock_event = MagicMock()
        mock_event.created_at = '2024-01-01'
        mock_event.performed_by = 1
        mock_event.from_status = 'pending'
        mock_event.to_status = 'completed'
        mock_event.notes = 'Test notes'

        with patch('services.clinical_context_service.db.session.execute') as mock_execute:
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_event]
            mock_execute.return_value = mock_result

            result = ClinicalContextService.get_timeline(1)

            assert len(result) == 1
            assert result[0]['timestamp'] == '2024-01-01'
            assert result[0]['actor'] == 'User #1'
            assert result[0]['action'] == 'pending -> completed'
            assert result[0]['detail'] == 'Test notes'

    def test_get_timeline_system_actor(self):
        """Test get_timeline with no performed_by (system actor)."""
        mock_event = MagicMock()
        mock_event.created_at = '2024-01-01'
        mock_event.performed_by = None
        mock_event.from_status = 'pending'
        mock_event.to_status = 'completed'
        mock_event.notes = None

        with patch('services.clinical_context_service.db.session.execute') as mock_execute:
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_event]
            mock_execute.return_value = mock_result

            result = ClinicalContextService.get_timeline(1)

            assert len(result) == 1
            assert result[0]['actor'] == 'System'
            assert result[0]['detail'] == ''


if __name__ == '__main__':
    pytest.main([__file__, '-v'])