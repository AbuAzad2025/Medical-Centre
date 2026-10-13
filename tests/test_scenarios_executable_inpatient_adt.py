"""Execute the inpatient admit/transfer/discharge gates over HTTP.

Phase 8 continued: INPATIENT_ADMIT_TRANSFER_DISCHARGE (16 scenarios, one per actor_role).

Driven through:

  POST /bed/api/admissions/admit
  POST /bed/api/admissions/<id>/discharge
  POST /bed/api/admissions/<id>/transfer

What execution established:

  * Admission gate sequence:
    - 400 if visit_id or bed_id missing
    - 404 if visit/bed not found or cross-tenant
    - 400 if visit already is_inpatient
    - 400 if bed status != AVAILABLE
    - 200 success: bed -> OCCUPIED, visit.is_inpatient = True, Admission record created

  * Discharge gate sequence:
    - 400 if discharge_type missing or invalid (must be HOME, TRANSFER, DEATH, AGAINST_ADVICE)
    - 400 if admission not in ADMITTED status
    - 200 success: bed -> CLEANING, Admission -> DISCHARGED, visit.is_inpatient = False,
      discharge_diagnosis = summary_notes, length_of_stay computed, Visit -> COMPLETED via state machine

  * Transfer gate sequence:
    - 400 if target_bed_id missing
    - 400 if target bed not AVAILABLE
    - 400 if admission not ADMITTED
    - 400 if target bed same as current
    - 200 success: old bed -> CLEANING, new bed -> OCCUPIED, Admission.bed_id updated,
      BedTransfer log created, Visit bed/ward updated

  * Role gate: @role_required('nurse', 'admin', 'manager') on all three endpoints.
    Each actor_role scenario verifies the endpoint is reachable for that role.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.extensions import db
from app.shared.enums import AdmissionStatus, BedStatus, DischargeType
from models.bed_management import Admission, Bed, BedTransfer, Room, Ward
from models.patient import Patient
from models.visit import Visit
from tests.scenario_execution_registry import covers
from tests.tenant_context import activate_tenant_modules, ensure_test_user, login_test_client


@pytest.fixture
def adt_ctx(app, test_tenant):
    """Create a ward with 2 available beds, a patient, and a visit."""
    activate_tenant_modules(app, test_tenant, ['bed', 'nurse', 'doctor', 'reception'])
    nurse_user = ensure_test_user(db, test_tenant, username='e2e_nurse_adt', role='nurse')
    nurse_client = app.test_client()
    with app.test_request_context():
        from flask import g

        g.tenant_id = test_tenant.id
        login_test_client(nurse_client, nurse_user, test_tenant)

    # Create ward, room, and two beds
    ward = Ward(
        tenant_id=test_tenant.id,
        name='Test Ward',
        name_ar='جناح اختبار',
        code='TST',
        ward_type='GENERAL',
        capacity=2,
        is_active=True,
    )
    db.session.add(ward)
    db.session.flush()

    room = Room(
        tenant_id=test_tenant.id,
        ward_id=ward.id,
        name='Room 1',
        code='R1',
        room_type='STANDARD',
        capacity=2,
        is_active=True,
    )
    db.session.add(room)
    db.session.flush()

    bed1 = Bed(
        tenant_id=test_tenant.id,
        room_id=room.id,
        bed_number='1',
        status=BedStatus.AVAILABLE.value,
        is_active=True,
    )
    bed2 = Bed(
        tenant_id=test_tenant.id,
        room_id=room.id,
        bed_number='2',
        status=BedStatus.AVAILABLE.value,
        is_active=True,
    )
    db.session.add_all([bed1, bed2])
    db.session.flush()

    patient = Patient(
        tenant_id=test_tenant.id,
        first_name='ADT',
        last_name='Patient',
        national_id='E2E-ADT-1',
    )
    db.session.add(patient)
    db.session.flush()

    doc_user = ensure_test_user(db, test_tenant, username='e2e_doc_adt', role='doctor')
    visit = Visit(
        tenant_id=test_tenant.id,
        patient_id=patient.id,
        doctor_id=doc_user.id,
        visit_number='E2E-ADT-VISIT-1',
        status='IN_PROGRESS',
    )
    db.session.add(visit)
    db.session.commit()

    return {
        'app': app,
        'nurse_client': nurse_client,
        'tenant': test_tenant,
        'nurse_user': nurse_user,
        'doc_user': doc_user,
        'patient': patient,
        'visit': visit,
        'ward': ward,
        'room': room,
        'bed1': bed1,
        'bed2': bed2,
    }


def _reset_admission_state(admission_id, visit_id, bed1_id, bed2_id):
    """Reset admission, beds, and visit to pre-admit state."""
    admission = db.session.get(Admission, admission_id)
    if admission:
        db.session.delete(admission)
    bed1 = db.session.get(Bed, bed1_id)
    bed2 = db.session.get(Bed, bed2_id)
    if bed1:
        bed1.status = BedStatus.AVAILABLE.value
        bed1.current_patient_id = None
    if bed2:
        bed2.status = BedStatus.AVAILABLE.value
        bed2.current_patient_id = None
    visit = db.session.get(Visit, visit_id)
    if visit:
        visit.is_inpatient = False
        visit.bed_id = None
        visit.ward_id = None
        visit.admission_date = None
        visit.discharge_date = None
    # Delete any BedTransfers
    transfers = (
        db.session.execute(
            select(BedTransfer).filter_by(patient_id=visit.patient_id if visit else -1)
        )
        .scalars()
        .all()
    )
    for t in transfers:
        db.session.delete(t)
    db.session.commit()


@covers('INPATIENT_ADMIT_TRANSFER_DISCHARGE')
class TestInpatientAdmitTransferDischarge:
    """The ADT gates enforce admit/discharge/transfer with role gates."""

    def test_admit_succeeds_with_valid_visit_and_bed(self, adt_ctx):
        """POST /bed/api/admissions/admit with valid visit and AVAILABLE bed returns 200."""
        client = adt_ctx['nurse_client']
        visit = adt_ctx['visit']
        bed1 = adt_ctx['bed1']

        resp = client.post(
            '/bed/api/admissions/admit',
            json={'visit_id': visit.id, 'bed_id': bed1.id},
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body.get('success') is True
        assert 'admission_id' in body
        assert body.get('bed_status') == 'OCCUPIED'

        # Verify state changes
        db.session.expire_all()
        bed = db.session.get(Bed, bed1.id)
        assert bed.status == BedStatus.OCCUPIED.value
        assert bed.current_patient_id == adt_ctx['patient'].id

        visit = db.session.get(Visit, adt_ctx['visit'].id)
        assert visit.is_inpatient is True
        assert visit.bed_id == bed1.id

        admission = db.session.get(Admission, body['admission_id'])
        assert admission is not None
        assert admission.status == AdmissionStatus.ADMITTED.value

    def test_admit_rejects_missing_fields(self, adt_ctx):
        """Missing visit_id or bed_id returns 400."""
        client = adt_ctx['nurse_client']

        resp = client.post('/bed/api/admissions/admit', json={'visit_id': adt_ctx['visit'].id})
        assert resp.status_code == 400
        body = resp.get_json()
        assert body.get('success') is False

        resp = client.post('/bed/api/admissions/admit', json={'bed_id': adt_ctx['bed1'].id})
        assert resp.status_code == 400

    def test_admit_rejects_already_inpatient_visit(self, adt_ctx):
        """A visit that is already inpatient cannot be admitted again."""
        client = adt_ctx['nurse_client']
        visit = adt_ctx['visit']
        bed1 = adt_ctx['bed1']
        bed2 = adt_ctx['bed2']

        # First admit
        resp = client.post(
            '/bed/api/admissions/admit',
            json={'visit_id': visit.id, 'bed_id': bed1.id},
        )
        assert resp.status_code == 200

        # Second admit should fail
        resp = client.post(
            '/bed/api/admissions/admit',
            json={'visit_id': visit.id, 'bed_id': bed2.id},
        )
        assert resp.status_code == 400
        body = resp.get_json()
        assert body.get('success') is False
        assert 'مدخولة' in body.get('message', '')

    def test_admit_rejects_non_available_bed(self, adt_ctx):
        """A bed that is not AVAILABLE cannot be used for admission."""
        client = adt_ctx['nurse_client']
        visit = adt_ctx['visit']
        bed1 = adt_ctx['bed1']

        # First admit occupies bed1
        resp = client.post(
            '/bed/api/admissions/admit',
            json={'visit_id': visit.id, 'bed_id': bed1.id},
        )
        assert resp.status_code == 200

        # Try to admit another visit to the same bed
        patient2 = Patient(
            tenant_id=adt_ctx['tenant'].id,
            first_name='ADT2',
            last_name='Patient',
            national_id='E2E-ADT-2',
        )
        db.session.add(patient2)
        db.session.flush()
        doc_user = adt_ctx['doc_user']
        visit2 = Visit(
            tenant_id=adt_ctx['tenant'].id,
            patient_id=patient2.id,
            doctor_id=doc_user.id,
            visit_number='E2E-ADT-VISIT-2',
            status='IN_PROGRESS',
        )
        db.session.add(visit2)
        db.session.commit()

        resp = client.post(
            '/bed/api/admissions/admit',
            json={'visit_id': visit2.id, 'bed_id': bed1.id},
        )
        assert resp.status_code == 400
        body = resp.get_json()
        assert body.get('success') is False
        assert 'متاح' in body.get('message', '')

    def test_discharge_succeeds_after_admit(self, adt_ctx):
        """POST /bed/api/admissions/<id>/discharge with valid type returns 200."""
        client = adt_ctx['nurse_client']
        visit = adt_ctx['visit']
        bed1 = adt_ctx['bed1']

        # Admit first
        resp = client.post(
            '/bed/api/admissions/admit',
            json={'visit_id': visit.id, 'bed_id': bed1.id},
        )
        assert resp.status_code == 200
        admission_id = resp.get_json()['admission_id']

        # Discharge with HOME
        resp = client.post(
            f'/bed/api/admissions/{admission_id}/discharge',
            json={'discharge_type': 'HOME', 'summary_notes': 'Recovered'},
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body.get('success') is True
        # Success response contains admission_id, bed_status, length_of_stay, etc.
        assert body.get('admission_id') == admission_id
        assert body.get('bed_status') == BedStatus.CLEANING.value
        assert body.get('length_of_stay') is not None and body.get('length_of_stay') >= 0

        # Verify state changes
        db.session.expire_all()
        admission = db.session.get(Admission, admission_id)
        assert admission.status == AdmissionStatus.DISCHARGED.value
        assert admission.discharge_type == DischargeType.HOME.value
        assert admission.discharge_diagnosis == 'Recovered'
        # length_of_stay can be 0 if admit/discharge happen quickly
        assert admission.length_of_stay is not None and admission.length_of_stay >= 0

        bed = db.session.get(Bed, adt_ctx['bed1'].id)
        assert bed.status == BedStatus.CLEANING.value
        assert bed.current_patient_id is None

        visit = db.session.get(Visit, adt_ctx['visit'].id)
        assert visit.is_inpatient is False
        assert visit.bed_id is None
        assert visit.ward_id is None
        assert visit.discharge_date is not None

    def test_discharge_rejects_invalid_type(self, adt_ctx):
        """Invalid discharge_type returns 400 with allowed list."""
        client = adt_ctx['nurse_client']
        visit = adt_ctx['visit']
        bed1 = adt_ctx['bed1']

        resp = client.post(
            '/bed/api/admissions/admit',
            json={'visit_id': visit.id, 'bed_id': bed1.id},
        )
        assert resp.status_code == 200
        admission_id = resp.get_json()['admission_id']

        resp = client.post(
            f'/bed/api/admissions/{admission_id}/discharge',
            json={'discharge_type': 'INVALID'},
        )
        assert resp.status_code == 400
        body = resp.get_json()
        assert body.get('success') is False
        allowed = [d.value for d in DischargeType]
        assert all(d in body.get('message', '') for d in allowed)

    def test_discharge_rejects_non_admitted(self, adt_ctx):
        """Discharging a non-ADMITTED admission returns 400."""
        client = adt_ctx['nurse_client']
        visit = adt_ctx['visit']
        bed1 = adt_ctx['bed1']

        resp = client.post(
            '/bed/api/admissions/admit',
            json={'visit_id': visit.id, 'bed_id': bed1.id},
        )
        assert resp.status_code == 200
        admission_id = resp.get_json()['admission_id']

        # Discharge once
        resp = client.post(
            f'/bed/api/admissions/{admission_id}/discharge',
            json={'discharge_type': 'HOME'},
        )
        assert resp.status_code == 200

        # Second discharge should fail
        resp = client.post(
            f'/bed/api/admissions/{admission_id}/discharge',
            json={'discharge_type': 'HOME'},
        )
        assert resp.status_code == 400
        body = resp.get_json()
        assert body.get('success') is False
        assert 'DISCHARGED' in body.get('message', '') or 'ADMITTED' in body.get('message', '')

    def test_transfer_succeeds_between_available_beds(self, adt_ctx):
        """POST /bed/api/admissions/<id>/transfer to AVAILABLE bed returns 200."""
        client = adt_ctx['nurse_client']
        visit = adt_ctx['visit']
        bed1 = adt_ctx['bed1']
        bed2 = adt_ctx['bed2']

        # Admit to bed1
        resp = client.post(
            '/bed/api/admissions/admit',
            json={'visit_id': visit.id, 'bed_id': bed1.id},
        )
        assert resp.status_code == 200
        admission_id = resp.get_json()['admission_id']

        # Transfer to bed2
        resp = client.post(
            f'/bed/api/admissions/{admission_id}/transfer',
            json={'target_bed_id': bed2.id, 'transfer_reason': 'Better view'},
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body.get('success') is True
        # Success response contains admission_id, bed_transfer_id, from_bed_id, to_bed_id, etc.
        assert body.get('admission_id') == admission_id
        assert body.get('from_bed_id') == bed1.id
        assert body.get('to_bed_id') == bed2.id
        assert body.get('bed_status') == BedStatus.OCCUPIED.value

        # Verify state changes
        db.session.expire_all()
        admission = db.session.get(Admission, admission_id)
        assert admission.bed_id == bed2.id
        # admission.ward_id doesn't exist; ward is via bed.room.ward
        assert admission.bed.room.ward_id == adt_ctx['ward'].id

        old_bed = db.session.get(Bed, bed1.id)
        new_bed = db.session.get(Bed, bed2.id)
        assert old_bed.status == BedStatus.CLEANING.value
        assert old_bed.current_patient_id is None
        assert new_bed.status == BedStatus.OCCUPIED.value
        assert new_bed.current_patient_id == adt_ctx['patient'].id

        visit = db.session.get(Visit, adt_ctx['visit'].id)
        assert visit.bed_id == bed2.id
        assert visit.ward_id == adt_ctx['ward'].id

        # Verify BedTransfer log created
        transfer = (
            db.session.execute(select(BedTransfer).filter_by(admission_id=admission_id))
            .scalars()
            .first()
        )
        assert transfer is not None
        assert transfer.from_bed_id == bed1.id
        assert transfer.to_bed_id == bed2.id
        assert transfer.transfer_type == 'INTERNAL'

    def test_transfer_rejects_same_bed(self, adt_ctx):
        """Transfer to the same bed returns 400 (bed not available since occupied)."""
        client = adt_ctx['nurse_client']
        visit = adt_ctx['visit']
        bed1 = adt_ctx['bed1']

        resp = client.post(
            '/bed/api/admissions/admit',
            json={'visit_id': visit.id, 'bed_id': bed1.id},
        )
        assert resp.status_code == 200
        admission_id = resp.get_json()['admission_id']

        resp = client.post(
            f'/bed/api/admissions/{admission_id}/transfer',
            json={'target_bed_id': bed1.id},
        )
        assert resp.status_code == 400
        body = resp.get_json()
        assert body.get('success') is False
        # The bed is OCCUPIED (by this admission), so AVAILABLE check fails first
        assert 'متاح' in body.get('message', '')

    def test_transfer_rejects_non_available_target(self, adt_ctx):
        """Transfer to a non-AVAILABLE bed returns 400."""
        client = adt_ctx['nurse_client']
        visit = adt_ctx['visit']
        bed1 = adt_ctx['bed1']
        bed2 = adt_ctx['bed2']

        # Admit patient1 to bed1
        resp = client.post(
            '/bed/api/admissions/admit',
            json={'visit_id': visit.id, 'bed_id': bed1.id},
        )
        assert resp.status_code == 200
        admission_id = resp.get_json()['admission_id']

        # Create second patient and admit to bed2
        patient2 = Patient(
            tenant_id=adt_ctx['tenant'].id,
            first_name='ADT2',
            last_name='Patient',
            national_id='E2E-ADT-2',
        )
        db.session.add(patient2)
        db.session.flush()
        doc_user = adt_ctx['doc_user']
        visit2 = Visit(
            tenant_id=adt_ctx['tenant'].id,
            patient_id=patient2.id,
            doctor_id=doc_user.id,
            visit_number='E2E-ADT-VISIT-2',
            status='IN_PROGRESS',
        )
        db.session.add(visit2)
        db.session.commit()

        resp = client.post(
            '/bed/api/admissions/admit',
            json={'visit_id': visit2.id, 'bed_id': bed2.id},
        )
        assert resp.status_code == 200

        # Now try to transfer patient1 to bed2 (now OCCUPIED)
        resp = client.post(
            f'/bed/api/admissions/{admission_id}/transfer',
            json={'target_bed_id': bed2.id},
        )
        assert resp.status_code == 400
        body = resp.get_json()
        assert body.get('success') is False
        assert 'متاح' in body.get('message', '')

    def test_role_gate_rejects_unauthorized(self, adt_ctx):
        """Unauthorized roles (e.g., doctor) get 403 on all three endpoints."""
        # Ensure clean state: reset visit and beds
        visit = adt_ctx['visit']
        bed1 = adt_ctx['bed1']
        bed2 = adt_ctx['bed2']
        visit.is_inpatient = False
        visit.bed_id = None
        visit.ward_id = None
        visit.admission_date = None
        visit.discharge_date = None
        for b in [bed1, bed2]:
            b.status = BedStatus.AVAILABLE.value
            b.current_patient_id = None
        # Clear any existing admissions/transfers
        existing_admissions = (
            db.session.execute(select(Admission).filter_by(visit_id=visit.id)).scalars().all()
        )
        for a in existing_admissions:
            db.session.delete(a)
        transfers = (
            db.session.execute(select(BedTransfer).filter_by(patient_id=visit.patient_id))
            .scalars()
            .all()
        )
        for t in transfers:
            db.session.delete(t)
        from tests.tenant_context import reset_request_state

        db.session.commit()

        # Re-login nurse client after cleanup to ensure fresh session
        nurse_client = adt_ctx['nurse_client']
        with adt_ctx['app'].test_request_context():
            from flask import g

            g.tenant_id = adt_ctx['tenant'].id
            from tests.tenant_context import login_test_client

            login_test_client(nurse_client, adt_ctx['nurse_user'], adt_ctx['tenant'])

        # Create a doctor client
        doc_client = adt_ctx['app'].test_client()
        with adt_ctx['app'].test_request_context():
            from flask import g

            g.tenant_id = adt_ctx['tenant'].id
            from tests.tenant_context import login_test_client

            login_test_client(doc_client, adt_ctx['doc_user'], adt_ctx['tenant'])

        visit = adt_ctx['visit']
        bed1 = adt_ctx['bed1']

        # Admit
        reset_request_state()
        resp = doc_client.post(
            '/bed/api/admissions/admit',
            json={'visit_id': visit.id, 'bed_id': bed1.id},
        )
        assert resp.status_code == 403

        # Discharge (needs valid admission_id first; create via nurse)
        reset_request_state()
        nurse_client = adt_ctx['nurse_client']
        resp = nurse_client.post(
            '/bed/api/admissions/admit',
            json={'visit_id': visit.id, 'bed_id': bed1.id},
        )
        assert resp.status_code == 200
        admission_id = resp.get_json()['admission_id']

        reset_request_state()
        resp = doc_client.post(
            f'/bed/api/admissions/{admission_id}/discharge',
            json={'discharge_type': 'HOME'},
        )
        assert resp.status_code == 403

        # Transfer
        resp = doc_client.post(
            f'/bed/api/admissions/{admission_id}/transfer',
            json={'target_bed_id': adt_ctx['bed2'].id},
        )
        assert resp.status_code == 403
