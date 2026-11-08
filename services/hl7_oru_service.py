"""HL7 ORU^R01 Service — Parse lab results from HL7 ORU messages."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from app.extensions import db
from models.lab_request import LabRequest, LabResult
from models.patient import Patient

logger = logging.getLogger(__name__)


class HL7ORUService:
    """Parse HL7 ORU^R01 messages and create lab results."""

    @staticmethod
    def parse_oru_message(raw: str, tenant_id: int | None = None) -> dict[str, Any]:
        """Parse an ORU^R01 message and extract patient, order, and result info."""
        from services.hl7_mllp_service import _parse_er7

        segments = _parse_er7(raw)
        result = {
            'patient_id': None,
            'order_id': None,
            'results': [],
            'errors': [],
        }

        # Extract patient ID from PID-3
        pid_segs = segments.get('PID', [])
        if pid_segs:
            pid = pid_segs[0]
            if len(pid) > 3:
                pid3 = pid[3]
                # Try to find patient by ID
                try:
                    patient = db.session.get(Patient, int(pid3))
                    if patient:
                        result['patient_id'] = patient.id
                except (ValueError, TypeError):
                    result['errors'].append(f'Invalid patient ID: {pid3}')

        # Extract order ID from OBR-3
        obr_segs = segments.get('OBR', [])
        if obr_segs:
            obr = obr_segs[0]
            if len(obr) > 3:
                obr3 = obr[3]
                try:
                    lab_request = (
                        db.session.execute(select(LabRequest).filter_by(id=int(obr3)))
                        .scalars()
                        .first()
                    )
                    if lab_request:
                        result['order_id'] = lab_request.id
                except (ValueError, TypeError):
                    result['errors'].append(f'Invalid order ID: {obr3}')

        # Extract results from OBX segments
        obx_segs = segments.get('OBX', [])
        for obx in obx_segs:
            if len(obx) < 6:
                continue
            test_field = obx[3] if len(obx) > 3 else ''
            value = obx[5] if len(obx) > 5 else ''
            unit = obx[6] if len(obx) > 6 else ''
            ref_range = obx[7] if len(obx) > 7 else ''
            abnormal_flag = obx[8] if len(obx) > 8 else ''
            # OBX-3 is 'code^text^coding_system'; keep the code for the
            # mandatory test_code column and the text for display.
            parts = test_field.split('^')
            test_code = (parts[0] or test_field).strip() or 'UNKNOWN'
            test_name = (parts[1] if len(parts) > 1 else test_field).strip() or test_code

            result['results'].append(
                {
                    'test_code': test_code,
                    'test_name': test_name,
                    'value': value,
                    'unit': unit,
                    'reference_range': ref_range,
                    'abnormal_flag': abnormal_flag,
                }
            )

        return result

    @staticmethod
    def create_results_from_oru(raw: str, tenant_id: int | None = None) -> dict[str, Any]:
        """Parse ORU message and create LabResult records."""
        parsed = HL7ORUService.parse_oru_message(raw, tenant_id)
        created = []
        errors = list(parsed['errors'])

        if not parsed['order_id']:
            errors.append('No valid order ID found in ORU message')
            return {'created': created, 'errors': errors}

        lab_request = db.session.get(LabRequest, parsed['order_id'])
        if not lab_request:
            errors.append(f'Lab request {parsed["order_id"]} not found')
            return {'created': created, 'errors': errors}

        created_objs = []
        for res in parsed['results']:
            try:
                lab_result = LabResult(
                    tenant_id=tenant_id or lab_request.tenant_id,
                    request_id=lab_request.id,
                    patient_id=parsed['patient_id'] or lab_request.patient_id,
                    test_code=res.get('test_code') or 'UNKNOWN',
                    test_name=res.get('test_name') or 'UNKNOWN',
                    value=res.get('value'),
                    unit=res.get('unit'),
                    reference_range=res.get('reference_range'),
                    is_critical=res['abnormal_flag'] in ('HH', 'LL', 'H', 'L'),
                    status='PENDING',
                )
                db.session.add(lab_result)
                created_objs.append(lab_result)
            except Exception as e:
                errors.append(f'Error creating result for {res["test_name"]}: {e}')

        if created_objs:
            try:
                db.session.flush()
                db.session.commit()
                # ids are only assigned after the flush, so collect them now
                created = [obj.id for obj in created_objs]
            except Exception as e:
                errors.append(f'Commit failed: {e}')
                db.session.rollback()

        return {'created': created, 'errors': errors}

    @staticmethod
    def handle_oru_message(segs: dict, raw: str) -> str | None:
        """Handler for HL7 ORU messages — creates lab results."""
        parsed = HL7ORUService.parse_oru_message(raw)
        if parsed['errors']:
            logger.warning('ORU parse errors: %s', parsed['errors'])
        if parsed['order_id'] and parsed['results']:
            result = HL7ORUService.create_results_from_oru(raw)
            logger.info('ORU created %d results', len(result['created']))
            return f'Created {len(result["created"])} results'
        return 'ORU received'
