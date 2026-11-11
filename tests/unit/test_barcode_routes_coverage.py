"""Coverage tests for routes.barcode_routes.py"""

from __future__ import annotations

import pytest

pytest_plugins = ['tests._isolated_tenant']


class TestBarcodeRoutes:
    def test_scan_page(self, app, client, login_as):
        login_as(client, 'bc_scan_user', 'nurse')
        resp = client.get('/barcode/scan')
        assert resp.status_code in (200, 302)

    def test_api_scan_missing_barcode(self, app, client, login_as):
        login_as(client, 'bc_scan2_user', 'nurse')
        resp = client.post(
            '/barcode/api/scan',
            json={},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is False

    def test_api_scan_not_found(self, app, client, login_as):
        login_as(client, 'bc_scan3_user', 'nurse')
        resp = client.post(
            '/barcode/api/scan',
            json={'barcode': 'NONEXISTENT-BARCODE'},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is False

    def test_api_scan_success(self, app, client, login_as):
        login_as(client, 'bc_scan4_user', 'nurse')
        from models.barcode_tracking import BarcodeRegistry
        from app.extensions import db

        registry = BarcodeRegistry(
            barcode_value='TEST-BARCODE-001',
            barcode_type='QR_CODE',
            entity_type='patient',
            entity_id=1,
            is_active=True,
        )
        db.session.add(registry)
        db.session.flush()
        # The request runs in its own app context (and therefore its own
        # session), so the registry has to be committed to be visible to it.
        db.session.commit()

        resp = client.post(
            '/barcode/api/scan',
            json={'barcode': 'TEST-BARCODE-001', 'action': 'VERIFY'},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True

    def test_api_scan_defaults_action_to_verify(self, app, client, login_as):
        """A scan without an explicit action is recorded as a VERIFY."""
        from app.extensions import db
        from models.barcode_tracking import BarcodeScanLog

        login_as(client, 'bc_scan5_user', 'nurse')

        resp = client.post(
            '/barcode/api/scan',
            json={'barcode': 'NONEXISTENT-BARCODE-DEFAULT'},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is False
        assert data['message'] == 'Barcode not found'

        log = (
            db.session.execute(
                db.select(BarcodeScanLog).where(
                    BarcodeScanLog.verification_result == 'NOT_FOUND'
                )
            )
            .scalars()
            .first()
        )
        assert log is not None
        assert log.scan_action == 'VERIFY'

    def test_registry_page(self, app, client, login_as):
        login_as(client, 'bc_reg_user', 'admin')
        resp = client.get('/barcode/registry')
        assert resp.status_code in (200, 302)

    def test_registry_with_filter(self, app, client, login_as):
        login_as(client, 'bc_reg2_user', 'admin')
        resp = client.get('/barcode/registry?entity_type=patient')
        assert resp.status_code in (200, 302)
