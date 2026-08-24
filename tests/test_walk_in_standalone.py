"""Standalone walk-in tests — create lab/radiology/pharmacy without visit."""

import uuid
from datetime import UTC, datetime

import pytest


@pytest.fixture()
def _walkin_env(app, db, test_tenant):
    """Patient + medication, NO visit required. Returns plain IDs."""
    from models.department import Department
    from models.medication import Medication
    from models.patient import Patient

    tag = uuid.uuid4().hex[:6]
    dept = Department(tenant_id=test_tenant.id, name=f'W-{tag}', name_ar=f'م-{tag}', is_active=True)
    db.session.add(dept)

    patient = Patient(
        tenant_id=test_tenant.id,
        first_name='WalkIn',
        last_name=tag,
        gender='M',
        phone='050' + str(uuid.uuid4().int % 10**7),
        first_name_ar='مباشر',
        last_name_ar='بدون موعد',
    )
    db.session.add(patient)
    db.session.flush()

    med = Medication(
        tenant_id=test_tenant.id,
        trade_name=f'Med-{tag}',
        scientific_name=f'S-{tag}',
        dosage_form='tablet',
        strength='500mg',
        price=10,
        stock_quantity=50,
        minimum_stock=10,
        category='general',
        is_active=True,
    )
    db.session.add(med)
    db.session.commit()

    return {
        'patient_id': patient.id,
        'medication_id': med.id,
        'dept_id': dept.id,
        'tenant_id': test_tenant.id,
        'tag': tag,
    }


def _make_requestor(db, tenant_id):
    """Create a unique requestor user per test."""
    from models.user import User

    uid = uuid.uuid4().hex[:8]
    u = User(
        tenant_id=tenant_id,
        username=f'req_{uid}',
        email=f'req_{uid}@test.local',
        full_name='Walk-In Requestor',
        role='reception',
        is_active=True,
    )
    u.set_password('x')
    db.session.add(u)
    db.session.commit()
    return u


class TestWalkInLabRequest:
    def test_create_lab_request_without_visit(self, app, db, _walkin_env):
        from models.lab_request import LabRequest

        u = _make_requestor(db, _walkin_env['tenant_id'])
        lr = LabRequest(
            tenant_id=_walkin_env['tenant_id'],
            patient_id=_walkin_env['patient_id'],
            visit_id=None,
            requested_by=u.id,
            status='REQUESTED',
            created_at=datetime.now(UTC),
        )
        db.session.add(lr)
        db.session.commit()
        assert lr.id > 0
        assert lr.visit_id is None

        fresh = db.session.get(LabRequest, lr.id)
        assert fresh.visit_id is None
        assert fresh.patient_id == _walkin_env['patient_id']


class TestWalkInRadiologyRequest:
    def test_create_radiology_request_without_visit(self, app, db, _walkin_env):
        from models.radiology_request import RadiologyRequest

        u = _make_requestor(db, _walkin_env['tenant_id'])
        rr = RadiologyRequest(
            tenant_id=_walkin_env['tenant_id'],
            patient_id=_walkin_env['patient_id'],
            visit_id=None,
            requested_by=u.id,
            status='REQUESTED',
            modality='XRAY',
            body_part='Chest',
            created_at=datetime.now(UTC),
        )
        db.session.add(rr)
        db.session.commit()
        assert rr.id > 0
        assert rr.visit_id is None


class TestWalkInPrescription:
    def test_create_prescription_without_visit(self, app, db, _walkin_env):
        from models.medication import Prescription

        u = _make_requestor(db, _walkin_env['tenant_id'])
        rx = Prescription(
            tenant_id=_walkin_env['tenant_id'],
            patient_id=_walkin_env['patient_id'],
            visit_id=None,
            doctor_id=u.id,
            prescription_number=f'RX-WI-{uuid.uuid4().hex[:8]}',
            status='active',
        )
        db.session.add(rx)
        db.session.commit()
        assert rx.id > 0
        assert rx.visit_id is None
