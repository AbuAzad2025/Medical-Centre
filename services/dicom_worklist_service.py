"""
DICOM Modality Worklist (MWL) Service — provides scheduled imaging orders to modalities.

Implements a lightweight MWL SCU/SCP abstraction:
- HTTP JSON worklist at /api/dicom/worklist (primary, no pynetdicom required)
- Optional pynetdicom MWL SCP on port 11112 if library is available and DICOM_MWL_ENABLED=true

Worklist items are derived from RadiologyRequest (status REQUESTED/IN_PROGRESS) joined to Patient.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

logger = logging.getLogger(__name__)


def _mwl_item_from_request(req, patient) -> dict[str, Any]:
    """Map RadiologyRequest + Patient to DICOM MWL entry."""
    # Scheduled Procedure Step
    return {
        'StudyInstanceUID': f'1.2.826.0.1.3680043.10.{req.id}.{int(datetime.now(UTC).timestamp())}',
        'Modality': (req.modality or 'OT').upper(),
        'ScheduledStationAETitle': os.environ.get('DICOM_MWL_AE_TITLE', 'MEDICAL_MWL'),
        'ScheduledProcedureStepStartDate': req.created_at.strftime('%Y%m%d')
        if req.created_at
        else datetime.now(UTC).strftime('%Y%m%d'),
        'ScheduledProcedureStepStartTime': req.created_at.strftime('%H%M%S')
        if req.created_at
        else datetime.now(UTC).strftime('%H%M%S'),
        'ScheduledProcedureStepDescription': req.body_part or req.notes or 'Radiology',
        'RequestedProcedureDescription': req.notes or '',
        'PatientName': patient.full_name if patient else f'Patient#{req.patient_id}',
        'PatientID': str(req.patient_id),
        'PatientBirthDate': patient.birth_date.strftime('%Y%m%d')
        if patient and patient.birth_date
        else '',
        'PatientSex': (patient.gender or 'O')[0].upper() if patient else 'O',
        'AccessionNumber': req.request_number or str(req.id),
        'RequestingPhysician': '',
        'ReferringPhysicianName': '',
        'StudyID': str(req.id),
    }


class DICOMWorklistService:
    @staticmethod
    def get_worklist(
        modality: str | None = None,
        station_ae: str | None = None,
        scheduled_date: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        from app.extensions import db
        from models.patient import Patient
        from models.radiology_request import RadiologyRequest

        q = select(RadiologyRequest).filter(
            RadiologyRequest.status.in_(['REQUESTED', 'IN_PROGRESS'])
        )
        if modality:
            q = q.filter(RadiologyRequest.modality == modality.upper())
        q = q.order_by(RadiologyRequest.created_at.desc()).limit(limit)
        reqs = db.session.execute(q).scalars().all()
        # Batch load patients
        pids = {r.patient_id for r in reqs}
        patients = {}
        if pids:
            rows = db.session.execute(select(Patient).filter(Patient.id.in_(pids))).scalars().all()
            patients = {p.id: p for p in rows}
        items = []
        for r in reqs:
            pat = patients.get(r.patient_id)
            item = _mwl_item_from_request(r, pat)
            if scheduled_date and item['ScheduledProcedureStepStartDate'] != scheduled_date:
                continue
            if station_ae and item['ScheduledStationAETitle'] != station_ae:
                # Still include if station filter not matching — modalities often query with own AE
                pass
            items.append(item)
        return items

    @staticmethod
    def get_worklist_for_patient(patient_id: int) -> list[dict[str, Any]]:
        from app.extensions import db
        from models.patient import Patient
        from models.radiology_request import RadiologyRequest

        q = select(RadiologyRequest).filter(
            RadiologyRequest.patient_id == patient_id,
            RadiologyRequest.status.in_(['REQUESTED', 'IN_PROGRESS']),
        )
        reqs = db.session.execute(q).scalars().all()
        patient = db.session.get(Patient, patient_id)
        return [_mwl_item_from_request(r, patient) for r in reqs]


# Optional pynetdicom MWL SCP — only if library installed and enabled
def _start_pynetdicom_mwl_scp():
    if os.environ.get('DICOM_MWL_ENABLED', 'false').lower() not in ('1', 'true', 'yes', 'on'):
        return None
    try:
        from pynetdicom import AE
        from pynetdicom.sop_class import ModalityWorklistInformationFind

        ae = AE(ae_title=os.environ.get('DICOM_MWL_AE_TITLE', 'MEDICAL_MWL'))
        ae.add_supported_context(ModalityWorklistInformationFind)

        def _handle_find(event):
            # event.identifier is a Dataset with query keys; we return all pending
            items = DICOMWorklistService.get_worklist(limit=50)
            # Convert dicts to pynetdicom Dataset if available
            try:
                from pydicom.dataset import Dataset

                for it in items:
                    ds = Dataset()
                    for k, v in it.items():
                        setattr(ds, k, v)
                    yield (0xFF00, ds)
            except Exception:
                return
            yield (0x0000, None)

        ae.start_server(
            ('0.0.0.0', int(os.environ.get('DICOM_MWL_PORT', '11112'))),
            block=False,
            evt_handlers=[(__import__('pynetdicom.events', fromlist=['EVT_C_FIND']), _handle_find)],
        )
        logger.info('DICOM MWL SCP started')
        return ae
    except ImportError:
        logger.info(
            'pynetdicom not installed — DICOM MWL SCP disabled, HTTP worklist remains available'
        )
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning('DICOM MWL SCP failed to start: %s', exc)
        return None


dicom_worklist_service = DICOMWorklistService()
