"""Regression tests for the LabResult column-name fixes.

Two services wrote `lab_result.entered_by` and read `result.result_value`,
fields that do not exist on the LabResult model. Both fixes map onto real
columns (performed_by / value).
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.extensions import db
from models.lab_request import LabResult
from services.fhir_service import FHIRService


class TestEnterResults:
    def test_entered_by_maps_to_performed_by(self, app, test_tenant):
        lab_result = LabResult(
            tenant_id=test_tenant.id,
            request_id=1,
            patient_id=1,
            test_code='CBC',
            test_name='Hemoglobin',
            is_critical=False,
        )
        from app.modules.workflows.lab import LabWorkflowService

        LabWorkflowService.enter_results(lab_result, {'value': '13.5', 'unit': 'g/dL'}, entered_by=42)
        assert lab_result.performed_by == 42
        assert lab_result.value == '13.5'
        assert lab_result.unit == 'g/dL'


class TestSerializeLabObservation:
    def test_real_lab_result_shape_does_not_crash(self, app, test_tenant):
        result = LabResult(
            tenant_id=test_tenant.id,
            request_id=1,
            patient_id=7,
            test_code='CBC',
            test_name='Hemoglobin',
            value='13.5',
            unit='g/dL',
            status='VALIDATED',
            is_critical=False,
        )
        observation = FHIRService.serialize_lab_observation(result)
        assert observation['resourceType'] == 'Observation'
        assert observation['valueQuantity']['value'] == '13.5'
        assert observation['valueQuantity']['unit'] == 'g/dL'
        assert observation['subject']['reference'] == 'Patient/7'

    def test_missing_value_omits_value_quantity(self, app, test_tenant):
        result = LabResult(
            tenant_id=test_tenant.id,
            request_id=1,
            patient_id=7,
            test_code='CBC',
            test_name='Hemoglobin',
            value=None,
            unit=None,
            status='PENDING',
            is_critical=False,
        )
        observation = FHIRService.serialize_lab_observation(result)
        assert 'valueQuantity' not in observation or observation.get('valueQuantity') is None
