"""Tests for services.hl7_oru_service module - HL7 ORU^R01 lab result parsing.

Covers parse_oru_message (PID-3, OBR-3, OBX extraction), create_results_from_oru
(create, errors, commit), and handle_oru_message.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.extensions import db
from models.lab_request import LabRequest, LabResult
from models.patient import Patient
from services.hl7_oru_service import HL7ORUService


def _make_patient(app, test_tenant):
    p = Patient(
        tenant_id=test_tenant.id,
        first_name='ORU',
        last_name='Patient',
        gender='F',
    )
    db.session.add(p)
    db.session.commit()
    return p.id


def _make_lab_request(app, test_tenant, patient_id):
    req = LabRequest(
        tenant_id=test_tenant.id,
        patient_id=patient_id,
        status='completed',
    )
    db.session.add(req)
    db.session.commit()
    return req.id


def _oru(patient_id=None, order_id=None, obx_rows: list | None = None):
    obx_rows = obx_rows if obx_rows is not None else [
        ('HGB^Hemoglobin', '13.5', 'g/dL', '12-16', 'N'),
    ]
    pid = f'PID|||{patient_id}||ORU^Patient' if patient_id is not None else 'PID|||bad-id||ORU^Patient'
    obr = f'OBR|||{order_id}' if order_id is not None else 'OBR|||bad-order^TestOrder'
    obx = '\r'.join(
        f'OBX||NM|{name}||{value}|{unit}|{ref}|{flag}'
        for name, value, unit, ref, flag in obx_rows
    )
    return f'MSH|^~\\&|LAB|HOSP|||20240101||ORU^R01|123|P|2.5\r{pid}\r{obr}\r{obx}'


class TestParseOruMessage:
    def test_parse_extracts_patient_order_and_results(self, app, test_tenant):
        patient_id = _make_patient(app, test_tenant)
        order_id = _make_lab_request(app, test_tenant, patient_id)
        raw = _oru(patient_id=patient_id, order_id=order_id, obx_rows=[
            ('Hemoglobin', '14.2', 'g/dL', '12-16', 'N'),
            ('Hematocrit', '42.0', '%', '37-47', 'N'),
        ])
        parsed = HL7ORUService.parse_oru_message(raw, tenant_id=test_tenant.id)
        assert parsed['patient_id'] == patient_id
        assert parsed['order_id'] == order_id
        assert len(parsed['results']) == 2
        assert parsed['results'][0]['test_code'] == 'Hemoglobin'
        assert parsed['results'][0]['test_name'] == 'Hemoglobin'
        assert parsed['results'][0]['value'] == '14.2'
        assert parsed['results'][0]['abnormal_flag'] == 'N'

    def test_parse_invalid_patient_id_records_error(self, app, test_tenant):
        raw = _oru(patient_id='not-a-number', order_id=1)
        parsed = HL7ORUService.parse_oru_message(raw, tenant_id=test_tenant.id)
        assert parsed['patient_id'] is None
        assert any('Invalid patient ID' in e for e in parsed['errors'])

    def test_parse_invalid_order_id_records_error(self, app, test_tenant):
        patient_id = _make_patient(app, test_tenant)
        raw = _oru(patient_id=patient_id, order_id='not-a-number')
        parsed = HL7ORUService.parse_oru_message(raw, tenant_id=test_tenant.id)
        assert parsed['order_id'] is None
        assert any('Invalid order ID' in e for e in parsed['errors'])

    def test_parse_missing_pid_and_obr(self, app, test_tenant):
        raw = 'MSH|^~\\&|LAB|HOSP|||20240101||ORU^R01|123|P|2.5\rOBX||CBC^X^L|||10|N'
        parsed = HL7ORUService.parse_oru_message(raw, tenant_id=test_tenant.id)
        assert parsed['patient_id'] is None
        assert parsed['order_id'] is None
        assert parsed['errors'] == []

    def test_parse_short_obx_segments_are_skipped(self, app, test_tenant):
        raw = 'MSH|^~\\&|LAB|HOSP|||20240101||ORU^R01\rOBX||A'
        parsed = HL7ORUService.parse_oru_message(raw, tenant_id=test_tenant.id)
        assert parsed['results'] == []

    def test_parse_order_not_found_yields_none(self, app, test_tenant):
        patient_id = _make_patient(app, test_tenant)
        raw = _oru(patient_id=patient_id, order_id=999999)
        parsed = HL7ORUService.parse_oru_message(raw, tenant_id=test_tenant.id)
        assert parsed['order_id'] is None

    def test_parse_critical_flag_is_preserved(self, app, test_tenant):
        patient_id = _make_patient(app, test_tenant)
        order_id = _make_lab_request(app, test_tenant, patient_id)
        raw = _oru(patient_id=patient_id, order_id=order_id, obx_rows=[
            ('Potassium', '2.1', 'mmol/L', '3.5-5.0', 'LL'),
        ])
        parsed = HL7ORUService.parse_oru_message(raw, tenant_id=test_tenant.id)
        assert parsed['results'][0]['abnormal_flag'] == 'LL'


class TestCreateResultsFromOru:
    def test_creates_lab_results(self, app, test_tenant):
        patient_id = _make_patient(app, test_tenant)
        order_id = _make_lab_request(app, test_tenant, patient_id)
        raw = _oru(patient_id=patient_id, order_id=order_id, obx_rows=[
            ('Hemoglobin', '15.0', 'g/dL', '13-17', 'N'),
        ])
        result = HL7ORUService.create_results_from_oru(raw, tenant_id=test_tenant.id)
        try:
            assert result['created']
            assert result['errors'] == []
            rows = db.session.execute(
                select(LabResult).where(LabResult.request_id == order_id)
            ).scalars().all()
            assert len(rows) == 1
            assert rows[0].test_name == 'Hemoglobin'
            assert rows[0].is_critical is False
        finally:
            db.session.query(LabResult).delete()
            db.session.commit()

    def test_critical_flag_sets_is_critical(self, app, test_tenant):
        patient_id = _make_patient(app, test_tenant)
        order_id = _make_lab_request(app, test_tenant, patient_id)
        raw = _oru(patient_id=patient_id, order_id=order_id, obx_rows=[
            ('Potassium', '1.9', 'mmol/L', '3.5-5.0', 'LL'),
        ])
        result = HL7ORUService.create_results_from_oru(raw, tenant_id=test_tenant.id)
        try:
            rows = db.session.execute(
                select(LabResult).where(LabResult.request_id == order_id)
            ).scalars().all()
            assert rows[0].is_critical is True
            assert result['errors'] == []
        finally:
            db.session.query(LabResult).delete()
            db.session.commit()

    def test_no_order_id_returns_error_without_creating_rows(self, app, test_tenant):
        raw = _oru(patient_id=1, order_id='not-a-number')
        result = HL7ORUService.create_results_from_oru(raw, tenant_id=test_tenant.id)
        assert result['created'] == []
        assert any('No valid order ID' in e for e in result['errors'])

    def test_missing_lab_request_returns_error(self, app, test_tenant):
        patient_id = _make_patient(app, test_tenant)
        raw = _oru(patient_id=patient_id, order_id=999999)
        result = HL7ORUService.create_results_from_oru(raw, tenant_id=test_tenant.id)
        assert result['created'] == []
        assert any('order ID' in e for e in result['errors'])


class TestHandleOruMessage:
    def test_returns_summary_when_order_and_results_present(self, app, test_tenant):
        patient_id = _make_patient(app, test_tenant)
        order_id = _make_lab_request(app, test_tenant, patient_id)
        raw = _oru(patient_id=patient_id, order_id=order_id, obx_rows=[
            ('Hemoglobin', '14.0', 'g/dL', '13-17', 'N'),
        ])
        summary = HL7ORUService.handle_oru_message({}, raw)
        try:
            assert 'Created 1 results' in summary
        finally:
            db.session.query(LabResult).delete()
            db.session.commit()

    def test_returns_received_when_no_order_id(self, app, test_tenant):
        raw = 'MSH|^~\\&|LAB|HOSP|||20240101||ORU^R01|123|P|2.5\rOBX||CBC^X^L|||10|N'
        assert HL7ORUService.handle_oru_message({}, raw) == 'ORU received'
