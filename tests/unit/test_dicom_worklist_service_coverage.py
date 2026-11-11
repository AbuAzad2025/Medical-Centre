"""Coverage tests for services.dicom_worklist_service.py"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import patch

import pytest

pytest_plugins = ['tests._isolated_tenant']


def _make_patient(db, tenant_id, first_name='Patient', last_name='Test', gender='M', birth_date=None):
    from models.patient import Patient

    p = Patient(
        tenant_id=tenant_id,
        first_name=first_name,
        last_name=last_name,
        gender=gender,
        birth_date=birth_date,
        phone=f'050{datetime.now(UTC).strftime("%H%M%S%f")[-7:]}',
    )
    db.session.add(p)
    db.session.flush()
    return p


def _make_radiology_request(db, tenant_id, patient_id, modality='CT', status='REQUESTED',
                            body_part='Chest', notes='Test notes', request_number=None):
    from models.radiology_request import RadiologyRequest

    r = RadiologyRequest(
        tenant_id=tenant_id,
        patient_id=patient_id,
        modality=modality,
        status=status,
        body_part=body_part,
        notes=notes,
        request_number=request_number,
        created_at=datetime.now(UTC),
    )
    db.session.add(r)
    db.session.flush()
    return r


class TestDICOMWorklistService:
    def test_get_worklist_empty(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        from services.dicom_worklist_service import DICOMWorklistService

        result = DICOMWorklistService.get_worklist()
        assert result == []

    def test_get_worklist_with_requests(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        from services.dicom_worklist_service import DICOMWorklistService

        patient = _make_patient(db, test_tenant.id, first_name='MWL', last_name='Patient', gender='M')
        _make_radiology_request(db, test_tenant.id, patient.id, modality='CT', status='REQUESTED')

        result = DICOMWorklistService.get_worklist()
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]['Modality'] == 'CT'
        assert result[0]['PatientID'] == str(patient.id)

    def test_get_worklist_filter_modality(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        from services.dicom_worklist_service import DICOMWorklistService

        patient = _make_patient(db, test_tenant.id)
        _make_radiology_request(db, test_tenant.id, patient.id, modality='MRI', status='REQUESTED')

        result = DICOMWorklistService.get_worklist(modality='CT')
        assert len(result) == 0

        result = DICOMWorklistService.get_worklist(modality='MRI')
        assert len(result) == 1

    def test_get_worklist_for_patient(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        from services.dicom_worklist_service import DICOMWorklistService

        patient = _make_patient(db, test_tenant.id)
        _make_radiology_request(db, test_tenant.id, patient.id, modality='XR', status='IN_PROGRESS')

        result = DICOMWorklistService.get_worklist_for_patient(patient.id)
        assert len(result) == 1
        assert result[0]['PatientID'] == str(patient.id)

    def test_get_worklist_for_patient_no_requests(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        from services.dicom_worklist_service import DICOMWorklistService

        patient = _make_patient(db, test_tenant.id)
        result = DICOMWorklistService.get_worklist_for_patient(patient.id)
        assert result == []

    def test_mwl_item_from_request(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        from services.dicom_worklist_service import _mwl_item_from_request

        patient = _make_patient(db, test_tenant.id, birth_date=datetime(1980, 1, 1).date())
        req = _make_radiology_request(db, test_tenant.id, patient.id, modality='US', status='REQUESTED',
                                      body_part='Abdomen', notes='Ultrasound abdomen')

        item = _mwl_item_from_request(req, patient)
        assert item['Modality'] == 'US'
        assert item['PatientName'] == patient.full_name
        assert item['PatientID'] == str(patient.id)
        assert item['PatientSex'] == 'M'
        assert item['ScheduledProcedureStepDescription'] == 'Abdomen'
        assert item['RequestedProcedureDescription'] == 'Ultrasound abdomen'

    def test_mwl_item_from_request_no_patient(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        from services.dicom_worklist_service import _mwl_item_from_request

        patient = _make_patient(db, test_tenant.id)
        req = _make_radiology_request(db, test_tenant.id, patient.id, modality='CT', status='REQUESTED')

        # The patient row is missing (deleted / not yet joined): the entry has to
        # still be produced from the request alone.
        item = _mwl_item_from_request(req, None)
        assert item['PatientName'] == f'Patient#{patient.id}'
        assert item['PatientID'] == str(patient.id)
        assert item['PatientSex'] == 'O'
        assert item['PatientBirthDate'] == ''

    def test_get_worklist_in_progress(self, app, db, test_tenant):
        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        from services.dicom_worklist_service import DICOMWorklistService

        patient = _make_patient(db, test_tenant.id)
        _make_radiology_request(db, test_tenant.id, patient.id, modality='CT', status='IN_PROGRESS')
        _make_radiology_request(db, test_tenant.id, patient.id, modality='CT', status='DONE')

        result = DICOMWorklistService.get_worklist(modality='CT')
        # Only REQUESTED and IN_PROGRESS should be included
        assert len(result) == 1
        assert result[0]['Modality'] == 'CT'
