"""Execute the diagnosis journey over real HTTP, and the problem list beside it.

Phase 3b. The diagnosis form is the most-edited screen in a clinic: a doctor
opens it, types what they found, saves, is interrupted, comes back, changes a
word and saves again. It is also the one that writes the patient's permanent
record. What matters therefore is not only whether the first save works but what
the second one does to the first, which is the question this module asks.

Everything is driven through ``POST /doctor/diagnosis/<visit_id>`` and
``POST /api/patients/<id>/problems/add`` and asserted on rows.

What execution established:

  * The first save is correct. The visit carries the complaint, the diagnosis, the
    treatment plan and the vitals, and a MedicalRecord is written for it.

  * A second save destroys the first. The follow-up date, the vitals and the
    clinical notes are each written from the form rather than merged with what is
    already on the visit, so a save that omits a field clears it. A doctor who
    saves twice and leaves the vitals blank on the second pass erases the vitals
    they took ten minutes earlier, with no warning and no way to recover.

  * Every save appends to the clinical record instead of revising it. Three saves
    produce three MedicalRecords with the same title and the same details, and the
    visit notes carry three copies of the same memo. The record a patient carries
    for life grows a duplicate every time anybody saves.

  * The problem list writes cleanly, and accepts its own types and severities.
"""

from __future__ import annotations

import json

import pytest
from flask import g
from sqlalchemy import func, select

from app.extensions import db
from models.medical_record import MedicalRecord
from tests.scenario_execution_registry import covers


@pytest.fixture
def consult(app, test_tenant):
    """A doctor, a patient and a visit in progress that the doctor still owns."""
    from tests.tenant_context import activate_tenant_modules, ensure_test_user, login_test_client

    activate_tenant_modules(app, test_tenant, ['doctor'])
    user = ensure_test_user(db, test_tenant, username='e2e_dx_doctor', role='doctor')
    client = app.test_client()
    with app.test_request_context():
        g.tenant_id = test_tenant.id
        login_test_client(client, user, test_tenant)

    from models.patient import Patient
    from models.visit import Visit

    patient = Patient(
        tenant_id=test_tenant.id,
        first_name='Dx',
        last_name='Patient',
        national_id='E2E-DX-1',
    )
    db.session.add(patient)
    db.session.flush()
    visit = Visit(
        tenant_id=test_tenant.id,
        patient_id=patient.id,
        doctor_id=user.id,
        visit_number='E2E-DX-VISIT-1',
        status='IN_PROGRESS',
    )
    db.session.add(visit)
    db.session.commit()
    return {
        'app': app,
        'client': client,
        'tenant': test_tenant,
        'doctor': user,
        'patient': patient,
        'visit': visit,
    }


def _save_diagnosis(client, visit_id, **fields):
    """POST the diagnosis form with only the fields named."""
    payload = {
        'chief_complaint': '',
        'symptoms': '',
        'diagnosis': '',
        'differential_diagnosis': '',
        'treatment_plan': '',
        'follow_up_notes': '',
        'follow_up_required': '',
        'follow_up_date': '',
        'notes': '',
        'blood_pressure': '',
        'heart_rate': '',
        'temperature': '',
        'respiratory_rate': '',
    }
    payload.update(fields)
    return client.post(f'/doctor/diagnosis/{visit_id}', data=payload, follow_redirects=False)


def _fresh(app, tenant, visit):
    from tests.tenant_context import refresh_scoped

    return refresh_scoped(app, tenant, visit)


def _vitals(visit):
    return json.loads(visit.vital_signs) if visit.vital_signs else {}


@covers('DIAGNOSIS_AND_PROBLEM_LIST')
class TestTheFirstSaveIsCorrect:
    """The ordinary case, pinned so the findings below are about the second save."""

    def test_a_saved_diagnosis_lands_on_the_visit_and_in_the_record(self, consult):
        client, visit = consult['client'], consult['visit']

        _save_diagnosis(
            client,
            visit.id,
            chief_complaint='headache and dizziness',
            symptoms='two days',
            diagnosis='migraine',
            treatment_plan='paracetamol, rest',
            blood_pressure='120/80',
            heart_rate='72',
        )

        fresh = _fresh(consult['app'], consult['tenant'], visit)
        assert fresh.diagnosis == 'migraine', f'diagnosis stored as {fresh.diagnosis!r}'
        assert fresh.chief_complaint == 'headache and dizziness'
        assert fresh.treatment_plan == 'paracetamol, rest'

        recorded = (
            db.session.execute(select(MedicalRecord).filter_by(visit_id=visit.id)).scalars().all()
        )
        assert len(recorded) == 1, f'expected one medical record, found {len(recorded)}'
        assert 'migraine' in (recorded[0].details or ''), (
            f'the medical record does not carry the diagnosis: {recorded[0].details!r}'
        )


@covers('DIAGNOSIS_AND_PROBLEM_LIST')
class TestASecondSaveDoesNotDestroyTheFirst:
    """Re-saving is the normal way a consultation is finished, not an edge case.

    Each case saves once with a field populated and then saves again with the same
    form left blank for that field, which is what happens when a doctor comes back
    to correct one word. The field should survive; three of them do not.
    """

    def test_the_follow_up_date_survives_a_second_save(self, consult):
        """A follow-up date booked on the first save is still there on the second.

        The handler assigns visit.follow_up_date from the form on every save, and
        assigns None when the field is empty, so the second save clears it. The
        follow-up itself is real work: a FollowUpRequest is created from this date
        the first time, and it then points at nothing.
        """
        client, visit = consult['client'], consult['visit']

        _save_diagnosis(
            client,
            visit.id,
            diagnosis='migraine',
            follow_up_required='on',
            follow_up_date='2026-11-30',
            follow_up_notes='review in four weeks',
        )
        first = _fresh(consult['app'], consult['tenant'], visit)
        assert first.follow_up_date is not None, (
            'the follow-up date did not save in the first place, so this case would '
            'pass for the wrong reason'
        )
        booked = str(first.follow_up_date)

        _save_diagnosis(client, visit.id, diagnosis='migraine, probably')

        second = _fresh(consult['app'], consult['tenant'], visit)
        assert second.follow_up_date is not None, (
            f'the follow-up date {booked} was cleared by a second save that did not '
            f'mention it. The handler assigns the field from the form every time and '
            f'sets it to None when empty, so re-saving silently cancels a booked '
            f'follow-up. Only clear it when the form says so.'
        )

    def test_the_vitals_survive_a_second_save(self, consult):
        """Vitals taken during the consultation are not erased by later typing.

        A nurse or a doctor records the vitals, then the doctor types the diagnosis
        and saves. The form renders blank vitals unless it is told otherwise, and the
        handler writes the whole dict back, so the vitals are replaced with four
        nulls.
        """
        client, visit = consult['client'], consult['visit']

        _save_diagnosis(
            client, visit.id, diagnosis='migraine', blood_pressure='120/80', heart_rate='72'
        )
        first = _fresh(consult['app'], consult['tenant'], visit)
        recorded = _vitals(first)
        assert recorded.get('blood_pressure') == '120/80', (
            f'the vitals did not save in the first place ({recorded!r}), so this case '
            f'would pass for the wrong reason'
        )

        _save_diagnosis(client, visit.id, diagnosis='migraine, probably')

        second = _fresh(consult['app'], consult['tenant'], visit)
        after = _vitals(second)
        assert after.get('blood_pressure') == '120/80', (
            f'the vitals were cleared by a second save that did not mention them: '
            f'{after!r}. vital_signs is overwritten wholesale with whatever the form '
            f'carries, and a blank field becomes None. Merge the vitals instead.'
        )

    def test_the_notes_are_not_appended_once_per_save(self, consult):
        """Saving three times leaves one memo on the visit, not three.

        The handler appends the free-text note to visit.notes on every save. The
        note is the one field that is genuinely append-shaped, so it accumulates
        silently and there is no sign in the interface that it is growing.
        """
        client, visit = consult['client'], consult['visit']

        for _ in range(3):
            _save_diagnosis(client, visit.id, diagnosis='migraine', notes='patient advised to rest')

        fresh = _fresh(consult['app'], consult['tenant'], visit)
        occurrences = (fresh.notes or '').count('patient advised to rest')
        assert occurrences == 1, (
            f'the note appears {occurrences} times in visit.notes after three saves of '
            f'the same text. Each save appends, so a consultation saved repeatedly '
            f'fills the notes with copies of itself.'
        )


@covers('DIAGNOSIS_AND_PROBLEM_LIST')
class TestTheRecordIsRevisedRatherThanDuplicated:
    def test_saving_twice_does_not_write_two_identical_medical_records(self, consult):
        """One consultation, one record.

        Every save constructs a new MedicalRecord titled 'تشخيص طبي' from the current
        form contents, with nothing to distinguish a revision from a new observation.
        Saving twice leaves two records that a clinician reading the history cannot
        tell apart.
        """
        client, visit = consult['client'], consult['visit']

        _save_diagnosis(client, visit.id, diagnosis='migraine')
        _save_diagnosis(client, visit.id, diagnosis='migraine, probably')

        records = (
            db.session.execute(select(MedicalRecord).filter_by(visit_id=visit.id)).scalars().all()
        )
        assert len(records) == 1, (
            f'the visit has {len(records)} medical records after two saves of the same '
            f'consultation. The record is constructed fresh on every save, so editing '
            f'the diagnosis appends a duplicate instead of revising the entry.'
        )


@covers('DIAGNOSIS_AND_PROBLEM_LIST')
class TestTheProblemListIsWrittenCleanly:
    """The other half of the template: the longitudinal problem list."""

    def _reception(self, consult):
        from tests.tenant_context import ensure_test_user, login_test_client

        user = ensure_test_user(db, consult['tenant'], username='e2e_problem_rec', role='reception')
        client = consult['app'].test_client()
        with consult['app'].test_request_context():
            g.tenant_id = consult['tenant'].id
            login_test_client(client, user, consult['tenant'])
        return client

    def test_a_problem_is_added_to_the_patient(self, consult):
        """A problem recorded at reception belongs to that patient and is ACTIVE."""
        from models.problem_list import PatientProblem

        client = self._reception(consult)
        patient = consult['patient']

        resp = client.post(
            f'/reception/api/patients/{patient.id}/problems/add',
            json={
                'problem_description': 'type 2 diabetes',
                'problem_type': 'CHRONIC',
                'severity': 'MODERATE',
            },
        )
        assert resp.status_code == 200, f'adding a problem answered {resp.status_code}'
        body = resp.get_json()
        assert body.get('success') is True, f'the endpoint reported {body!r}'

        rows = (
            db.session.execute(select(PatientProblem).filter_by(patient_id=patient.id))
            .scalars()
            .all()
        )
        assert len(rows) == 1, f'expected one problem, found {len(rows)}'
        assert rows[0].problem_description == 'type 2 diabetes'
        assert rows[0].status == 'ACTIVE', f'new problem is {rows[0].status!r}'

    def test_a_problem_without_a_description_is_refused(self, consult):
        """The one guard on this endpoint, asserted so it cannot be lost."""
        client = self._reception(consult)

        resp = client.post(
            f'/reception/api/patients/{consult["patient"].id}/problems/add',
            json={'problem_description': '   '},
        )
        assert resp.status_code == 400, (
            f'a blank problem was answered {resp.status_code} instead of 400'
        )

    def test_a_problem_cannot_be_added_to_a_patient_outside_this_tenant(self, consult):
        """The tenant check runs before the insert, so this is a 404 and not a write."""
        from models.problem_list import PatientProblem

        client = self._reception(consult)

        resp = client.post(
            '/reception/api/patients/999999/problems/add',
            json={'problem_description': 'should not be written'},
        )
        assert resp.status_code == 404, (
            f'a problem against a patient outside this tenant answered {resp.status_code} '
            f'instead of 404'
        )
        written = db.session.execute(
            select(func.count())
            .select_from(PatientProblem)
            .filter_by(problem_description='should not be written')
        ).scalar()
        assert not written, 'a problem was written for a patient outside this tenant'
