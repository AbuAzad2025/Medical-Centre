"""
Tests for lab barcode generation, scanning, and workflow (Phase 4)
"""
import base64
import secrets
from datetime import datetime, timezone

import pytest


class TestBarcodeService:
    def test_generate_lab_barcode_format(self, app):
        from services.barcode_service import generate_lab_barcode
        barcode_val, b64_img = generate_lab_barcode(1, 42)
        assert barcode_val.startswith("LAB-1-42-")
        assert len(b64_img) > 100
        png_bytes = base64.b64decode(b64_img)
        assert png_bytes[:8] == b'\x89PNG\r\n\x1a\n'

    def test_register_in_barcode_registry(self, app, test_tenant):
        from services.barcode_service import register_in_barcode_registry
        from app_factory import db
        from models.barcode_tracking import BarcodeRegistry
        barcode_val = f'TEST-{secrets.token_hex(8)}'
        register_in_barcode_registry(barcode_val, lab_request_id=99,
                                     generated_by_id=None, tenant_id=test_tenant.id)
        db.session.commit()
        reg = BarcodeRegistry.query.filter_by(barcode_value=barcode_val).first()
        assert reg is not None
        assert reg.entity_type == 'SPECIMEN'
        assert reg.barcode_type == 'QR_CODE'
        assert reg.entity_id == 99

    def test_setup_barcode_for_lab_request(self, app, test_tenant, test_patient, test_visit):
        from models.lab_request import LabRequest
        from services.barcode_service import setup_barcode_for_lab_request
        from app_factory import db
        from models.barcode_tracking import BarcodeRegistry
        lr = LabRequest(tenant_id=test_tenant.id, patient_id=test_patient.id,
                        visit_id=test_visit.id, status='REQUESTED')
        db.session.add(lr)
        db.session.flush()
        setup_barcode_for_lab_request(lr, tenant_id=test_tenant.id)
        db.session.commit()
        assert lr.barcode is not None
        assert lr.barcode.startswith(f"LAB-{lr.id}-{test_patient.id}-")
        assert lr.barcode_image is not None
        reg = BarcodeRegistry.query.filter_by(entity_type='SPECIMEN', entity_id=lr.id).first()
        assert reg is not None


class TestBarcodeScanEndpoint:
    def test_scan_collect(self, app, db, lab_auth_client, lab_request_with_barcode):
        barcode_val = lab_request_with_barcode.barcode
        resp = lab_auth_client.post(f'/lab/barcode/scan/{barcode_val}',
                                    json={'action': 'COLLECT'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        assert data['status'] == 'COLLECTED'
        from app_factory import db as _db
        _db.session.refresh(lab_request_with_barcode)
        assert lab_request_with_barcode.status == 'COLLECTED'
        assert lab_request_with_barcode.collection_time is not None

    def test_scan_receive_after_collect(self, app, db, lab_auth_client, lab_request_with_barcode):
        barcode_val = lab_request_with_barcode.barcode
        lab_auth_client.post(f'/lab/barcode/scan/{barcode_val}',
                             json={'action': 'COLLECT'})
        resp = lab_auth_client.post(f'/lab/barcode/scan/{barcode_val}',
                                    json={'action': 'RECEIVE'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'RECEIVED'
        from app_factory import db as _db
        _db.session.refresh(lab_request_with_barcode)
        assert lab_request_with_barcode.status == 'RECEIVED'
        assert lab_request_with_barcode.received_time is not None

    def test_scan_nonexistent_barcode(self, app, db, lab_auth_client):
        resp = lab_auth_client.post('/lab/barcode/scan/DOES-NOT-EXIST',
                                    json={'action': 'COLLECT'})
        assert resp.status_code == 404

    def test_scan_get_redirects_to_worklist(self, app, db, lab_auth_client, lab_request_with_barcode):
        barcode_val = lab_request_with_barcode.barcode
        resp = lab_auth_client.get(f'/lab/barcode/scan/{barcode_val}')
        assert resp.status_code == 302
        assert f'/lab/worklist/request/{lab_request_with_barcode.id}' in resp.headers['Location']

    def test_scan_get_nonexistent(self, app, db, lab_auth_client):
        resp = lab_auth_client.get('/lab/barcode/scan/NONEXISTENT')
        assert resp.status_code == 404


class TestBarcodePrintEndpoint:
    def test_print_page_renders(self, app, db, lab_auth_client, lab_request_with_barcode):
        resp = lab_auth_client.get(f'/lab/barcode/print/{lab_request_with_barcode.id}')
        assert resp.status_code == 200
        html = resp.data.decode('utf-8')
        assert 'data:image/png;base64,' in html

    def test_print_nonexistent_request(self, app, db, lab_auth_client):
        resp = lab_auth_client.get('/lab/barcode/print/99999')
        assert resp.status_code == 404

    def test_print_regenerates_if_missing(self, app, db, lab_auth_client, test_tenant):
        from models.lab_request import LabRequest
        from app_factory import db as _db
        from models.patient import Patient
        from models.visit import Visit
        p = Patient(tenant_id=test_tenant.id, first_name='Test', last_name='User',
                    phone='+970599999999')
        _db.session.add(p)
        _db.session.flush()
        v = Visit(tenant_id=test_tenant.id, patient_id=p.id, status='active')
        _db.session.add(v)
        _db.session.flush()
        lr = LabRequest(tenant_id=test_tenant.id, patient_id=p.id, visit_id=v.id, status='REQUESTED')
        _db.session.add(lr)
        _db.session.commit()
        assert lr.barcode is None
        resp = lab_auth_client.get(f'/lab/barcode/print/{lr.id}')
        assert resp.status_code == 200
        _db.session.refresh(lr)
        assert lr.barcode is not None
        assert lr.barcode_image is not None


class TestWorkflowCollect:
    def test_collect_action_via_form(self, app, db, lab_auth_client, lab_request_with_barcode):
        resp = lab_auth_client.post(f'/lab/worklist/request/{lab_request_with_barcode.id}',
                                    data={'action': 'collect'})
        assert resp.status_code == 302
        from app_factory import db as _db
        _db.session.refresh(lab_request_with_barcode)
        assert lab_request_with_barcode.status == 'COLLECTED'

    def test_receive_action_sets_received_time(self, app, db, lab_auth_client, lab_request_with_barcode):
        lab_request_with_barcode.status = 'COLLECTED'
        from app_factory import db as _db
        _db.session.commit()
        resp = lab_auth_client.post(f'/lab/worklist/request/{lab_request_with_barcode.id}',
                                    data={'action': 'receive'})
        assert resp.status_code == 302
        _db.session.refresh(lab_request_with_barcode)
        assert lab_request_with_barcode.status == 'RECEIVED'
        assert lab_request_with_barcode.received_time is not None


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture(scope='function')
def test_patient(app, test_tenant):
    from models.patient import Patient
    from app_factory import db
    p = Patient(
        tenant_id=test_tenant.id,
        first_name='مريض',
        last_name='باركود',
        first_name_ar='مريض',
        last_name_ar='باركود',
        phone='+970599123456',
        gender='male',
    )
    db.session.add(p)
    db.session.commit()
    return p


@pytest.fixture(scope='function')
def test_visit(app, test_tenant, test_patient):
    from models.visit import Visit
    from app_factory import db
    v = Visit(
        tenant_id=test_tenant.id,
        patient_id=test_patient.id,
        visit_type='lab',
        status='active',
    )
    db.session.add(v)
    db.session.commit()
    return v


@pytest.fixture(scope='function')
def lab_request_with_barcode(app, test_tenant, test_patient, test_visit):
    from models.lab_request import LabRequest
    from services.barcode_service import setup_barcode_for_lab_request
    from app_factory import db
    lr = LabRequest(
        tenant_id=test_tenant.id,
        patient_id=test_patient.id,
        visit_id=test_visit.id,
        status='REQUESTED',
    )
    db.session.add(lr)
    db.session.flush()
    setup_barcode_for_lab_request(lr, tenant_id=test_tenant.id)
    db.session.commit()
    return lr


@pytest.fixture(scope='function')
def lab_user(app, test_tenant):
    from models.user import User
    from app_factory import db
    u = User.query.filter_by(username='lab_barcode_test').first()
    if not u:
        u = User(
            username='lab_barcode_test',
            email='lab.barcode@test.local',
            full_name='فني مختبر باركود',
            role='lab',
            is_active=True,
            tenant_id=test_tenant.id,
        )
        u.set_password('test123')
        db.session.add(u)
        db.session.commit()
    return u


@pytest.fixture(scope='function')
def lab_auth_client(app, client, lab_user, test_tenant):
    from app.core.rate_limiter import _shared_store
    _shared_store.clear()
    client.post('/auth/login', data={
        'username': 'lab_barcode_test',
        'password': 'test123',
        'tenant_slug': test_tenant.slug,
    })
    return client
