"""Tests for P2-001: Lab Order Vertical Slice."""

import pytest

from app_factory import db as _db
from app.shared.enums import OrderState
from models.lab_request import LabRequest, LabResult
from models.lab_test_catalog import LabTestCatalog
from models.patient import Patient
from models.user import User
from models.visit import Visit
from services.lab_service import LabService


@pytest.fixture(scope='function')
def lab_patient(app, test_tenant):
    p = Patient(
        tenant_id=test_tenant.id,
        first_name='Lab',
        last_name='Patient',
        phone='0500000010',
    )
    _db.session.add(p)
    _db.session.commit()
    return p


@pytest.fixture(scope='function')
def lab_doctor(app, test_tenant):
    u = User.query.filter_by(username='lab_doctor').first()
    if not u:
        u = User(
            username='lab_doctor',
            email='lab_doc@example.com',
            full_name='Dr. Lab Order',
            role='doctor',
            is_active=True,
            tenant_id=test_tenant.id,
        )
        u.set_password('test123')
        _db.session.add(u)
        _db.session.commit()
    return u


@pytest.fixture(scope='function')
def lab_visit(app, test_tenant, lab_patient, lab_doctor):
    v = Visit(
        tenant_id=test_tenant.id,
        patient_id=lab_patient.id,
        doctor_id=lab_doctor.id,
        status='IN_PROGRESS',
    )
    _db.session.add(v)
    _db.session.commit()
    return v


@pytest.fixture(scope='function')
def lab_catalog(app, test_tenant):
    items = []
    for code, name in [('CBC', 'CBC'), ('GLU', 'Glucose')]:
        c = LabTestCatalog.query.filter_by(
            tenant_id=test_tenant.id, code=code
        ).first()
        if not c:
            c = LabTestCatalog(
                tenant_id=test_tenant.id,
                code=code,
                name_ar=name,
                unit='mg/dL' if code == 'GLU' else None,
                default_reference_range='70-100' if code == 'GLU' else None,
                is_active=True,
            )
            _db.session.add(c)
        items.append(c)
    _db.session.commit()
    return items


class TestLabServiceCreateRequest:
    def test_creates_lab_request_and_results(self, lab_visit, lab_catalog, lab_doctor):
        test_ids = [c.id for c in lab_catalog]
        ok, result = LabService.create_request(
            visit_id=lab_visit.id,
            test_ids=test_ids,
            requested_by=lab_doctor.id,
            notes='Fasting',
            tenant_id=lab_visit.tenant_id,
        )
        assert ok is True
        _db.session.commit()

        req = LabRequest.query.get(result['lab_request_id'])
        assert req is not None
        assert req.visit_id == lab_visit.id
        assert req.patient_id == lab_visit.patient_id
        assert req.requested_by == lab_doctor.id
        assert req.status == 'REQUESTED'
        assert req.notes == 'Fasting'
        assert req.request_number.startswith('LR-')
        assert req.tenant_id == lab_visit.tenant_id

        results = LabResult.query.filter_by(request_id=req.id).all()
        assert len(results) == 2
        codes = {r.test_code for r in results}
        assert codes == {'CBC', 'GLU'}

    def test_rejects_unknown_test_ids(self, lab_visit, lab_catalog, lab_doctor):
        ok, result = LabService.create_request(
            visit_id=lab_visit.id,
            test_ids=[lab_catalog[0].id, 999999],
            requested_by=lab_doctor.id,
            tenant_id=lab_visit.tenant_id,
        )
        assert ok is False
        assert 'Unknown' in result['error']

    def test_rejects_empty_test_ids(self, lab_visit, lab_doctor):
        ok, result = LabService.create_request(
            visit_id=lab_visit.id,
            test_ids=[],
            requested_by=lab_doctor.id,
            tenant_id=lab_visit.tenant_id,
        )
        assert ok is False
        assert 'No test IDs' in result['error']


class TestDoctorLabRequestRoute:
    def test_creates_structured_lab_request(self, app, client, lab_visit, lab_doctor, lab_catalog, test_tenant):
        from tests.tenant_context import login_test_client

        login_test_client(client, lab_doctor, test_tenant)
        test_ids = [c.id for c in lab_catalog]
        resp = client.post(f'/doctor/lab-request/{lab_visit.id}', data={
            'test_ids': ','.join(str(i) for i in test_ids),
            'notes': 'Routine panel',
        })
        assert resp.status_code in (200, 302)

        req = LabRequest.query.filter_by(visit_id=lab_visit.id).first()
        assert req is not None
        assert req.status == 'REQUESTED'
        results = LabResult.query.filter_by(request_id=req.id).count()
        assert results == 2

    def test_free_text_mode_without_test_ids(self, app, client, lab_visit, lab_doctor, test_tenant):
        from tests.tenant_context import login_test_client

        login_test_client(client, lab_doctor, test_tenant)
        resp = client.post(f'/doctor/lab-request/{lab_visit.id}', data={
            'test_name': 'Custom blood test',
            'notes': 'Please check manually',
        })
        assert resp.status_code in (200, 302)
        assert LabRequest.query.filter_by(visit_id=lab_visit.id).count() == 0
        _db.session.refresh(lab_visit)
        assert lab_visit.lab_tests_ordered is True
        assert 'مذكرة تحاليل' in (lab_visit.notes or '')
