"""Tests for P2-003: Radiology Order Vertical Slice."""

import pytest

from app_factory import db as _db
from models.patient import Patient
from models.radiology_request import RadiologyRequest
from models.user import User
from models.visit import Visit
from services.radiology_service import RadiologyService


@pytest.fixture(scope='function')
def rad_patient(app, test_tenant):
    p = Patient(
        tenant_id=test_tenant.id,
        first_name='Rad',
        last_name='Patient',
        phone='0500000030',
    )
    _db.session.add(p)
    _db.session.commit()
    return p


@pytest.fixture(scope='function')
def rad_doctor(app, test_tenant):
    u = User.query.filter_by(username='rad_doctor').first()
    if not u:
        u = User(
            username='rad_doctor',
            email='rad_doc@example.com',
            full_name='Dr. Radiology',
            role='doctor',
            is_active=True,
            tenant_id=test_tenant.id,
        )
        u.set_password('test123')
        _db.session.add(u)
        _db.session.commit()
    return u


@pytest.fixture(scope='function')
def rad_visit(app, test_tenant, rad_patient, rad_doctor):
    v = Visit(
        tenant_id=test_tenant.id,
        patient_id=rad_patient.id,
        doctor_id=rad_doctor.id,
        status='IN_PROGRESS',
    )
    _db.session.add(v)
    _db.session.commit()
    return v


class TestRadiologyServiceCreateRequest:
    def test_creates_radiology_request(self, rad_visit, rad_doctor, test_tenant):
        ok, result = RadiologyService.create_request(
            visit_id=rad_visit.id,
            requested_by=rad_doctor.id,
            modality='XRAY',
            body_part='Chest',
            notes='PA view',
            tenant_id=test_tenant.id,
        )
        assert ok is True
        _db.session.commit()

        req = RadiologyRequest.query.get(result['radiology_request_id'])
        assert req is not None
        assert req.visit_id == rad_visit.id
        assert req.patient_id == rad_visit.patient_id
        assert req.requested_by == rad_doctor.id
        assert req.status == 'REQUESTED'
        assert req.modality == 'XRAY'
        assert req.body_part == 'Chest'
        assert req.tenant_id == test_tenant.id
        assert req.request_number.startswith('RAD-')

    def test_rejects_missing_visit(self, rad_doctor, test_tenant):
        ok, result = RadiologyService.create_request(
            visit_id=999999,
            requested_by=rad_doctor.id,
            modality='CT',
            tenant_id=test_tenant.id,
        )
        assert ok is False
        assert 'Visit not found' in result['error']


class TestDoctorRadiologyRequestRoute:
    def test_creates_structured_radiology_request(self, app, client, rad_visit, rad_doctor, test_tenant):
        from tests.tenant_context import login_test_client

        login_test_client(client, rad_doctor, test_tenant)
        resp = client.post(f'/doctor/radiology-request/{rad_visit.id}', data={
            'modality': 'XRAY',
            'body_part': 'Chest',
            'notes': 'PA view',
        })
        assert resp.status_code in (200, 302)

        req = RadiologyRequest.query.filter_by(visit_id=rad_visit.id).first()
        assert req is not None
        assert req.modality == 'XRAY'
        assert req.body_part == 'Chest'

    def test_free_text_mode_without_modality(self, app, client, rad_visit, rad_doctor, test_tenant):
        from tests.tenant_context import login_test_client

        login_test_client(client, rad_doctor, test_tenant)
        resp = client.post(f'/doctor/radiology-request/{rad_visit.id}', data={
            'test_name': 'Custom scan',
            'notes': 'Please schedule',
        })
        assert resp.status_code in (200, 302)
        assert RadiologyRequest.query.filter_by(visit_id=rad_visit.id).count() == 0
        _db.session.refresh(rad_visit)
        assert rad_visit.radiology_ordered is True
        assert 'مذكرة تصوير' in (rad_visit.notes or '')
