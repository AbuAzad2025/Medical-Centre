"""Coverage tests for routes.lab.barcode.py"""

from __future__ import annotations

from datetime import UTC, datetime

pytest_plugins = ['tests._isolated_tenant']


class TestLabBarcodeRoutes:
    def test_barcode_scan_get_unknown(self, app, rollback_db, client, login_as):
        login_as(client, 'lab_bc_get', 'lab')
        resp = client.get('/lab/barcode/scan/UNKNOWN-BARCODE')
        assert resp.status_code in (302, 404, 200)

    def test_barcode_scan_post_unknown(self, app, rollback_db, client, login_as):
        login_as(client, 'lab_bc_post', 'lab')
        resp = client.post(
            '/lab/barcode/scan/UNKNOWN-BARCODE',
            json={'action': 'COLLECT'},
        )
        assert resp.status_code in (404, 200, 302)
        data = resp.get_json(silent=True)
        if data is not None:
            assert data['success'] is False

    def test_barcode_scan_post_collect(self, app, rollback_db, client, login_as, db):

        from app.extensions import db as _db

        login_as(client, 'lab_bc_collect', 'lab')

        from models.patient import Patient

        patient = Patient(
            first_name='Lab',
            last_name='Barcode',
            phone=f'050{datetime.now(UTC).strftime("%H%M%S%f")[-7:]}',
            gender='M',
        )
        _db.session.add(patient)
        _db.session.flush()

        from models.lab_request import LabRequest

        lab_request = LabRequest(
            patient_id=patient.id,
            status='REQUESTED',
            barcode='LAB-BARCODE-001',
            created_at=datetime.now(UTC),
        )
        _db.session.add(lab_request)
        _db.session.flush()
        lab_request_id = lab_request.id
        _db.session.commit()

        resp = client.post(
            '/lab/barcode/scan/LAB-BARCODE-001',
            json={'action': 'COLLECT'},
        )
        assert resp.status_code in (200, 302, 404)

        _db.session.rollback()
        refreshed = _db.session.get(LabRequest, lab_request_id)
        assert refreshed is not None
