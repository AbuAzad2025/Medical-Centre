"""
Tests for services.admission_service.AdmissionService (Phase 3.3 ADT flow).

All DB work runs under ``rollback_db`` isolation against the local PostgreSQL
test database (postgres:123@localhost:5432/medical_test via .env TEST_DATABASE_URL).
"""

import types

import pytest
from flask import g
from sqlalchemy import select

from app.extensions import db
from models.bed_management import Admission, Bed, BedTransfer, Room, Ward
from models.patient import Patient
from models.user import User
from models.visit import Visit
from services.admission_service import AdmissionService
from services.visit_state_machine_service import VisitStateMachineService

TENANT_ID = 1


@pytest.fixture
def adtfxt(rollback_db, monkeypatch):
    db = rollback_db

    # Bundle / module-limit checks are no-ops for fixture seeding (mirrors
    # tests/test_prescription_service.py).
    monkeypatch.setattr('app.shared.tenant_filter._check_bundle_limits_on_create', lambda *_a, **_k: None)
    monkeypatch.setattr('app.shared.tenant_filter._check_bundle_limits_on_update', lambda *_a, **_k: None)

    # Tenant context expected by get_tenant_record() and the query-time filter.
    g.tenant_id = TENANT_ID
    db.session.info['_tenant_id'] = TENANT_ID

    def ward(name='ICU', code='ICU1'):
        w = Ward(name=name, code=code, tenant_id=TENANT_ID)
        db.session.add(w)
        db.session.commit()
        return w

    def room(ward_id, name='R1', code='R1'):
        r = Room(ward_id=ward_id, name=name, code=code, tenant_id=TENANT_ID)
        db.session.add(r)
        db.session.commit()
        return r

    def bed(room_id, number='B1', status='AVAILABLE'):
        b = Bed(
            room_id=room_id,
            bed_number=number,
            status=status,
            is_active=True,
            tenant_id=TENANT_ID,
        )
        db.session.add(b)
        db.session.commit()
        return b

    def patient(first='عائد', last='اختبار'):
        p = Patient(first_name=first, last_name=last, tenant_id=TENANT_ID)
        db.session.add(p)
        db.session.commit()
        return p

    def doctor(role='doctor'):
        u = User(
            username=f'dr_{role}_{__import__("uuid").uuid4().hex[:6]}',
            email=f'{role}@test.local',
            full_name=f'د.{role}',
            role=role,
            is_active=True,
            tenant_id=TENANT_ID,
        )
        u.set_password('ValidPass123!')
        db.session.add(u)
        db.session.commit()
        return u

    def visit(patient_id):
        v = Visit(patient_id=patient_id, tenant_id=TENANT_ID)
        db.session.add(v)
        db.session.commit()
        return v

    return types.SimpleNamespace(
        db=db,
        ward=ward,
        room=room,
        bed=bed,
        patient=patient,
        doctor=doctor,
        visit=visit,
    )


def test_create_admission_occupies_bed_and_links_visit(adtfxt):
    w = adtfxt.ward()
    r = adtfxt.room(w.id)
    b = adtfxt.bed(r.id, number='B-101')
    p = adtfxt.patient()
    v = adtfxt.visit(p.id)
    doc = adtfxt.doctor()

    result = AdmissionService.create_admission(
        visit_id=v.id, bed_id=b.id, user_id=doc.id, tenant_id=TENANT_ID
    )

    assert result['success'] is True
    assert result['status'] == 'ADMITTED'
    assert result['bed_status'] == 'OCCUPIED'

    admission = db.session.get(Admission, result['admission_id'])
    assert admission.bed_id == b.id
    assert admission.visit_id == v.id
    assert admission.admitting_doctor_id == doc.id
    assert admission.patient_id == p.id

    b2 = db.session.get(Bed, b.id)
    assert b2.status == 'OCCUPIED'
    assert b2.current_patient_id == p.id

    v2 = db.session.get(Visit, v.id)
    assert v2.is_inpatient is True
    assert v2.bed_id == b.id
    assert v2.ward_id == w.id
    assert v2.admission_date is not None


def test_create_admission_rejects_occupied_bed(adtfxt):
    w = adtfxt.ward()
    r = adtfxt.room(w.id)
    b = adtfxt.bed(r.id, number='B-102', status='OCCUPIED')
    v = adtfxt.visit(adtfxt.patient().id)

    result = AdmissionService.create_admission(
        visit_id=v.id, bed_id=b.id, user_id=1, tenant_id=TENANT_ID
    )
    assert result['success'] is False
    assert 'غير متاح' in result['message']


def test_create_admission_rejects_inpatient_visit(adtfxt):
    w = adtfxt.ward()
    r = adtfxt.room(w.id)
    b = adtfxt.bed(r.id)
    v = adtfxt.visit(adtfxt.patient().id)
    doc = adtfxt.doctor()

    AdmissionService.create_admission(
        visit_id=v.id, bed_id=b.id, user_id=doc.id, tenant_id=TENANT_ID
    )
    # second admit on same visit should be rejected
    result = AdmissionService.create_admission(
        visit_id=v.id, bed_id=b.id, user_id=doc.id, tenant_id=TENANT_ID
    )
    assert result['success'] is False


def test_discharge_releases_bed_syncs_visit(adtfxt):
    w = adtfxt.ward()
    r = adtfxt.room(w.id)
    b = adtfxt.bed(r.id, number='B-201')
    v = adtfxt.visit(adtfxt.patient().id)
    doc = adtfxt.doctor()
    # Put the visit into a completable state.
    VisitStateMachineService.ensure_in_progress(v)
    db.session.commit()

    admit = AdmissionService.create_admission(
        visit_id=v.id, bed_id=b.id, user_id=doc.id, tenant_id=TENANT_ID
    )
    admission_id = admit['admission_id']

    result = AdmissionService.process_discharge(
        admission_id=admission_id,
        discharge_type='HOME',
        summary_notes='التعافي التام',
        user_id=doc.id,
        tenant_id=TENANT_ID,
    )

    assert result['success'] is True
    assert result['status'] == 'DISCHARGED'
    assert result['bed_status'] == 'CLEANING'
    assert result['length_of_stay'] is not None and result['length_of_stay'] >= 0

    adm = db.session.get(Admission, admission_id)
    assert adm.discharge_type == 'HOME'
    assert adm.discharge_datetime is not None
    assert adm.is_active is False

    b2 = db.session.get(Bed, b.id)
    assert b2.status == 'CLEANING'
    assert b2.current_patient_id is None

    v2 = db.session.get(Visit, v.id)
    assert v2.is_inpatient is False
    assert v2.bed_id is None
    assert v2.discharge_date is not None
    # Discharge drives the visit to COMPLETED through the state machine.
    assert v2.status == 'COMPLETED'


def test_discharge_rejects_invalid_type(adtfxt):
    w = adtfxt.ward()
    r = adtfxt.room(w.id)
    b = adtfxt.bed(r.id)
    v = adtfxt.visit(adtfxt.patient().id)
    doc = adtfxt.doctor()
    admit = AdmissionService.create_admission(
        visit_id=v.id, bed_id=b.id, user_id=doc.id, tenant_id=TENANT_ID
    )
    result = AdmissionService.process_discharge(
        admission_id=admit['admission_id'],
        discharge_type='NOT_A_REAL_TYPE',
        summary_notes=None,
        user_id=doc.id,
        tenant_id=TENANT_ID,
    )
    assert result['success'] is False
    assert 'غير صالح' in result['message']


def test_transfer_logs_and_repoints_bed(adtfxt):
    w = adtfxt.ward()
    r1 = adtfxt.room(w.id, name='R-1', code='R-1')
    r2 = adtfxt.room(w.id, name='R-2', code='R-2')
    b_from = adtfxt.bed(r1.id, number='B-301')
    b_to = adtfxt.bed(r2.id, number='B-302')
    v = adtfxt.visit(adtfxt.patient().id)
    doc = adtfxt.doctor()

    admit = AdmissionService.create_admission(
        visit_id=v.id, bed_id=b_from.id, user_id=doc.id, tenant_id=TENANT_ID
    )
    admission_id = admit['admission_id']

    result = AdmissionService.process_transfer(
        admission_id=admission_id,
        target_bed_id=b_to.id,
        transfer_reason='تحسين العناية',
        user_id=doc.id,
        tenant_id=TENANT_ID,
    )

    assert result['success'] is True
    assert result['from_bed_id'] == b_from.id
    assert result['to_bed_id'] == b_to.id
    assert result['bed_status'] == 'OCCUPIED'

    adm = db.session.get(Admission, admission_id)
    assert adm.bed_id == b_to.id

    old_bed = db.session.get(Bed, b_from.id)
    assert old_bed.status == 'CLEANING'
    assert old_bed.current_patient_id is None

    new_bed = db.session.get(Bed, b_to.id)
    assert new_bed.status == 'OCCUPIED'
    assert new_bed.current_patient_id == v.patient_id

    v2 = db.session.get(Visit, v.id)
    assert v2.bed_id == b_to.id
    assert v2.ward_id == w.id

    transfers = db.session.execute(select(BedTransfer).filter_by(admission_id=admission_id)).scalars().all()
    assert len(transfers) == 1
    assert transfers[0].from_bed_id == b_from.id
    assert transfers[0].to_bed_id == b_to.id
    assert transfers[0].reason == 'تحسين العناية'


def test_transfer_rejects_occupied_target(adtfxt):
    w = adtfxt.ward()
    r = adtfxt.room(w.id)
    b1 = adtfxt.bed(r.id, number='B-401')
    b2 = adtfxt.bed(r.id, number='B-402', status='OCCUPIED')
    v = adtfxt.visit(adtfxt.patient().id)
    doc = adtfxt.doctor()
    admit = AdmissionService.create_admission(
        visit_id=v.id, bed_id=b1.id, user_id=doc.id, tenant_id=TENANT_ID
    )

    result = AdmissionService.process_transfer(
        admission_id=admit['admission_id'],
        target_bed_id=b2.id,
        transfer_reason=None,
        user_id=doc.id,
        tenant_id=TENANT_ID,
    )
    assert result['success'] is False
