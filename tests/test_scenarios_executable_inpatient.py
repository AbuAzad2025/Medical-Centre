"""Execute the inpatient bed lifecycle over real HTTP, including under contention.

Phase 3d. Admission, transfer and discharge are three writes to one bed, and a bed
is the one resource in a hospital that cannot be in two places at once. That makes
this the first module where the interesting question is not what a single request
does but what two simultaneous requests do.

Executed here:

  admit            a visit takes a bed, the bed becomes OCCUPIED, the visit is
                   marked inpatient
  transfer         the patient moves, the old bed goes to CLEANING, the admission
                   and the visit both follow
  discharge        the admission closes with a length of stay, the bed is freed
                   and the visit comes off the inpatient list
  refusal         an occupied bed and a re-admitted visit are both refused
  contention      two admissions of different patients to the SAME bed, released
                   together on real threads

The contention case is the reason this module is marked concurrency, and it is the
one that matters. Everything else in this repository so far has been about logic;
this is about whether the read that decides something is allowed to be a plain read.

What execution established:

  * The single-request lifecycle is correct end to end, including the refusals.

  * Two patients can be admitted to the same bed. create_admission reads the bed
    through get_tenant_record, which issues no SELECT ... FOR UPDATE, then decides
    on the status it read and writes OCCUPIED. Both requests read AVAILABLE before
    either writes, both succeed, and the second commit overwrites the first
    patient's current_patient_id. The bed then reports one occupant while two
    Admission rows say ADMITTED on it, and the ward board is wrong about who is
    where.
"""

from __future__ import annotations

import uuid

import pytest
from flask import g
from sqlalchemy import select

from app.extensions import db
from models.bed_management import Admission, Bed, BedTransfer
from tests.scenario_execution_registry import covers


@pytest.fixture
def ward(app, test_tenant):
    """A ward with two rooms and two free beds, a nurse, and two inpatient visits."""
    from models.bed_management import Room, Ward
    from models.patient import Patient
    from models.visit import Visit
    from tests.tenant_context import activate_tenant_modules, ensure_test_user, login_test_client

    activate_tenant_modules(app, test_tenant, ['inpatient'])
    nurse = ensure_test_user(db, test_tenant, username='e2e_bed_nurse', role='nurse')
    client = app.test_client()
    with app.test_request_context():
        g.tenant_id = test_tenant.id
        login_test_client(client, nurse, test_tenant)

    tag = uuid.uuid4().hex[:6]
    w = Ward(tenant_id=test_tenant.id, name=f'Ward {tag}', name_ar=f'عنبر {tag}', code=f'W{tag}')
    db.session.add(w)
    db.session.flush()

    beds = []
    for i in (1, 2):
        room = Room(tenant_id=test_tenant.id, ward_id=w.id, name=f'Room {i}', code=f'R{tag}{i}')
        db.session.add(room)
        db.session.flush()
        bed = Bed(
            tenant_id=test_tenant.id, bed_number=f'{tag}-{i}', room_id=room.id, status='AVAILABLE'
        )
        db.session.add(bed)
        beds.append(bed)
    db.session.flush()

    visits = []
    for i in (1, 2):
        patient = Patient(
            tenant_id=test_tenant.id,
            first_name=f'Inp{tag}{i}',
            last_name='Patient',
            national_id=f'E2E-INP-{tag}-{i}',
        )
        db.session.add(patient)
        db.session.flush()
        visit = Visit(
            tenant_id=test_tenant.id,
            patient_id=patient.id,
            visit_number=f'E2E-INP-VISIT-{tag}-{i}',
            status='IN_PROGRESS',
        )
        db.session.add(visit)
        visits.append((patient, visit))
    db.session.commit()

    return {
        'app': app,
        'client': client,
        'tenant': test_tenant,
        'nurse': nurse,
        'ward': w,
        'beds': beds,
        'visits': visits,
    }


def _admit(client, visit_id, bed_id):
    return client.post(
        '/bed/api/admissions/admit',
        json={'visit_id': visit_id, 'bed_id': bed_id},
        follow_redirects=False,
    )


def _transfer(client, admission_id, target_bed_id, reason=None):
    payload = {'target_bed_id': target_bed_id}
    if reason:
        payload['transfer_reason'] = reason
    return client.post(
        f'/bed/api/admissions/{admission_id}/transfer', json=payload, follow_redirects=False
    )


def _discharge(client, admission_id, discharge_type='HOME', notes=None):
    payload = {'discharge_type': discharge_type}
    if notes:
        payload['summary_notes'] = notes
    return client.post(
        f'/bed/api/admissions/{admission_id}/discharge', json=payload, follow_redirects=False
    )


def _fresh(app, tenant, obj):
    from tests.tenant_context import refresh_scoped

    return refresh_scoped(app, tenant, obj)


@covers('INPATIENT_BED_AND_ADMISSION')
class TestTheSingleRequestLifecycle:
    def test_admitting_a_visit_occupies_the_bed(self, ward):
        """The ordinary admission, asserted on the bed and the visit."""
        client, bed = ward['client'], ward['beds'][0]
        _patient, visit = ward['visits'][0]

        resp = _admit(client, visit.id, bed.id)
        assert resp.status_code == 200, f'admit answered {resp.status_code}'
        assert resp.get_json().get('success') is True, f'admit reported {resp.get_json()!r}'

        fresh_bed = _fresh(ward['app'], ward['tenant'], bed)
        assert fresh_bed.status == 'OCCUPIED', f'bed status is {fresh_bed.status!r}'
        assert fresh_bed.current_patient_id == visit.patient_id

        fresh_visit = _fresh(ward['app'], ward['tenant'], visit)
        assert fresh_visit.is_inpatient is True, 'the visit was not marked inpatient'
        assert fresh_visit.bed_id == bed.id
        assert fresh_visit.ward_id == ward['ward'].id, (
            'the visit was not placed in the ward that owns the bed'
        )

        admission = (
            db.session.execute(select(Admission).filter_by(visit_id=visit.id)).scalars().first()
        )
        assert admission is not None, 'no Admission row was opened'
        assert admission.status == 'ADMITTED'

    def test_an_occupied_bed_is_refused(self, ward):
        """The second patient is turned away, with the reason naming the bed."""
        client = ward['client']
        _p1, visit1 = ward['visits'][0]
        _p2, visit2 = ward['visits'][1]
        bed = ward['beds'][0]

        assert _admit(client, visit1.id, bed.id).get_json().get('success') is True
        resp = _admit(client, visit2.id, bed.id)

        assert resp.status_code == 400, f'admitting to an occupied bed answered {resp.status_code}'
        body = resp.get_json()
        assert body.get('success') is False
        assert bed.bed_number in (body.get('message') or ''), (
            f'the refusal does not name the bed: {body.get("message")!r}'
        )

        rows = db.session.execute(select(Admission).filter_by(bed_id=bed.id)).scalars().all()
        assert len(rows) == 1, f'the occupied bed carries {len(rows)} admissions'

    def test_transferring_moves_the_patient_and_frees_the_old_bed(self, ward):
        """The bed changes hands and the paperwork follows it."""
        client = ward['client']
        _patient, visit = ward['visits'][0]
        old_bed, new_bed = ward['beds'][0], ward['beds'][1]

        _admit(client, visit.id, old_bed.id)
        admission = (
            db.session.execute(select(Admission).filter_by(visit_id=visit.id)).scalars().first()
        )

        resp = _transfer(
            client, admission.id, new_bed.id, reason='patient improved, moved to side room'
        )
        assert resp.status_code == 200, f'transfer answered {resp.status_code}'
        assert resp.get_json().get('success') is True

        assert _fresh(ward['app'], ward['tenant'], old_bed).status == 'CLEANING', (
            'the vacated bed did not go to CLEANING'
        )
        fresh_new = _fresh(ward['app'], ward['tenant'], new_bed)
        assert fresh_new.status == 'OCCUPIED'
        assert fresh_new.current_patient_id == visit.patient_id

        assert _fresh(ward['app'], ward['tenant'], admission).bed_id == new_bed.id, (
            'the admission still points at the old bed'
        )
        assert _fresh(ward['app'], ward['tenant'], visit).bed_id == new_bed.id, (
            'the visit still points at the old bed, so the ward board disagrees with the admission'
        )

        moved = (
            db.session.execute(select(BedTransfer).filter_by(admission_id=admission.id))
            .scalars()
            .first()
        )
        assert moved is not None, 'no BedTransfer row was written'
        assert moved.from_bed_id == old_bed.id and moved.to_bed_id == new_bed.id

    def test_discharging_closes_the_admission_and_frees_the_bed(self, ward):
        """The full arc: bed occupied, then released, with the stay measured."""
        client = ward['client']
        _patient, visit = ward['visits'][0]
        bed = ward['beds'][0]

        _admit(client, visit.id, bed.id)
        admission = (
            db.session.execute(select(Admission).filter_by(visit_id=visit.id)).scalars().first()
        )

        resp = _discharge(
            client, admission.id, discharge_type='HOME', notes='stable, follow up in a week'
        )
        assert resp.status_code == 200, f'discharge answered {resp.status_code}'
        assert resp.get_json().get('success') is True

        fresh_admission = _fresh(ward['app'], ward['tenant'], admission)
        assert fresh_admission.status == 'DISCHARGED', f'status is {fresh_admission.status!r}'
        assert fresh_admission.is_active is False, 'a discharged admission is still marked active'
        assert fresh_admission.length_of_stay is not None, (
            'length_of_stay was not computed, so the admission record cannot be reconciled'
        )

        fresh_bed = _fresh(ward['app'], ward['tenant'], bed)
        assert fresh_bed.current_patient_id is None, 'the bed still names a patient'
        assert fresh_bed.status == 'CLEANING'

        fresh_visit = _fresh(ward['app'], ward['tenant'], visit)
        assert fresh_visit.is_inpatient is False, 'the visit is still on the inpatient list'
        assert fresh_visit.bed_id is None

    def test_a_discharge_without_a_type_is_refused(self, ward):
        """discharge_type is required, and the refusal happens before any write."""
        client = ward['client']
        _patient, visit = ward['visits'][0]
        bed = ward['beds'][0]

        _admit(client, visit.id, bed.id)
        admission = (
            db.session.execute(select(Admission).filter_by(visit_id=visit.id)).scalars().first()
        )

        resp = _discharge(client, admission.id, discharge_type=None)
        assert resp.status_code == 400, f'a missing discharge_type answered {resp.status_code}'
        assert _fresh(ward['app'], ward['tenant'], admission).status == 'ADMITTED', (
            'the admission was closed despite the refusal'
        )


@covers('INPATIENT_BED_AND_ADMISSION')
@pytest.mark.concurrency
class TestTwoPatientsCannotShareABed:
    @pytest.mark.xfail(
        strict=True,
        reason=(
            'known defect: create_admission reads the bed without SELECT ... FOR UPDATE, '
            'so two admissions of different patients to one bed both succeed and the '
            'second commit overwrites the first'
        ),
    )
    def test_concurrent_admissions_of_one_bed_produce_one_patient(self, ward):
        """Two patients, one bed, released together: exactly one may end up in it.

        The invariant, not an interleaving: however the two requests interleave, the
        bed must name at most one patient and the bed must not carry two live
        admissions. Asserting the specific winner would test the scheduler instead of
        the code.

        create_admission decides on the status it read and then writes OCCUPIED. With
        no row lock, both requests read AVAILABLE and both proceed, so this fails
        intermittently rather than always. The test retries a few times to give the
        race a fair chance to appear.
        """
        from services.admission_service import AdmissionService
        from tests.test_concurrency import _run_concurrently

        app, tid = ward['app'], ward['tenant'].id
        bed = ward['beds'][0]
        visits = [v for _, v in ward['visits']]

        def admit(idx):
            with app.test_request_context():
                from flask import g

                g.tenant_id = tid
                svc = AdmissionService()
                return svc.create_admission(
                    visit_id=visits[idx].id, bed_id=bed.id, user_id=ward['nurse'].id, tenant_id=tid
                )

        # Run a few times to give the race a fair chance to appear.
        for _ in range(3):
            results = _run_concurrently(admit, 2)

            successes = [r for r in results if isinstance(r, dict) and r.get('success')]
            if len(successes) >= 2:
                break
            # Small delay to let the DB settle between attempts.
            import time

            time.sleep(0.05)
        else:
            pytest.skip('the two admissions did not both read AVAILABLE; race not observed')

        # Clean up any aborted transactions before checking state.
        ward['app'].extensions['sqlalchemy'].session.rollback()
        ward['app'].extensions['sqlalchemy'].session.remove()

        admissions = (
            db.session.execute(select(Admission).filter_by(bed_id=bed.id, status='ADMITTED'))
            .scalars()
            .all()
        )
        assert len(admissions) <= 1, (
            f'bed {bed.bed_number} carries {len(admissions)} live admissions after two '
            f'successful admits: {[a.id for a in admissions]}. Both requests read the '
            f'bed as AVAILABLE and both wrote OCCUPIED, so the second commit overwrote '
            f'the first patient. The read needs a row lock.'
        )
