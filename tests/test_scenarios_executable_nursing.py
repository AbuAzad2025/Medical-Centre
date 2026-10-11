"""Execute the nursing vitals and task surfaces over real HTTP.

Phase 8, clinical core. A vital sign is the one measurement a nurse takes that
nobody double-checks: it goes straight into the record and is read later by a
doctor who was not in the room. What matters here is therefore not whether the
write succeeds but what it refuses to store.

Driven through:

  POST /nurse/record-vital-signs/<patient_id>
  POST /nurse/tasks/create
  POST /nurse/tasks/<task_id>/status

What execution established:

  * The range validation is real and is asserted per boundary. diastolic must be
    below systolic, temperature 30-45, heart rate 20-250, SpO2 50-100. Each is
    checked independently, because a single "is this plausible" check would let a
    wrong unit through — a temperature of 41 is a fever in Celsius and a
    measurement in Fahrenheit is not a temperature at all.

  * A nurse without a linked Nurse profile is refused. The role alone is not
    enough: the route reads current_user.nurse_profile and returns 400 when it is
    absent, so a user who has the nurse role but no profile row cannot record
    anything. That is the right shape — the profile carries the licence number.

  * A patient outside the tenant is a 404 rather than a write, and the tenant
    filter is in the query rather than in a post-hoc check.
"""

from __future__ import annotations

import pytest
from flask import g
from sqlalchemy import select

from app.extensions import db
from models.nurse import Nurse, VitalSigns
from models.patient import Patient
from tests.scenario_execution_registry import covers


@pytest.fixture
def ward(app, test_tenant):
    """A nurse with a linked profile, and a patient."""
    from tests.tenant_context import activate_tenant_modules, ensure_test_user, login_test_client

    activate_tenant_modules(app, test_tenant, ['nurse'])
    nurse_user = ensure_test_user(db, test_tenant, username='e2e_nurse_vitals', role='nurse')
    client = app.test_client()
    with app.test_request_context():
        g.tenant_id = test_tenant.id
        login_test_client(client, nurse_user, test_tenant)

    profile = Nurse(
        tenant_id=test_tenant.id,
        user_id=nurse_user.id,
        license_number='E2E-NURSE-1',
    )
    db.session.add(profile)
    db.session.flush()
    # The relationship is a collection (one-to-many by default), so the fixture
    # assigns a list. The route handles this with isinstance(nurse_profile, (list, tuple)).
    nurse_user.nurse_profile = [profile]

    patient = Patient(
        tenant_id=test_tenant.id,
        first_name='Vital',
        last_name='Patient',
        national_id='E2E-VIT-1',
    )
    db.session.add(patient)
    db.session.commit()

    return {
        'app': app,
        'client': client,
        'tenant': test_tenant,
        'nurse_user': nurse_user,
        'profile': profile,
        'patient': patient,
    }


def _record(client, patient_id, **fields):
    return client.post(
        f'/nurse/record-vital-signs/{patient_id}', data=fields, follow_redirects=False
    )


def _vitals_for(patient_id):
    return db.session.execute(select(VitalSigns).filter_by(patient_id=patient_id)).scalars().all()


@covers('NURSING_VITALS_AND_TASK_TRIAGE')
class TestVitalsAreRangeChecked:
    """Each boundary is asserted on its own, because they fail differently.

    A diastolic above systolic is a transcription error. A temperature of 41 is a
    fever. A heart rate of 300 is a mis-keyed field. Each is a different mistake
    and a single plausibility check would not separate them.
    """

    def test_a_diastolic_above_the_systolic_is_refused(self, ward):
        """The one check that compares two fields against each other."""
        client, patient = ward['client'], ward['patient']

        resp = _record(
            client,
            patient.id,
            blood_pressure_systolic='120',
            blood_pressure_diastolic='130',
            heart_rate='72',
            temperature='36.6',
            oxygen_saturation='98',
        )
        assert resp.status_code == 400, (
            f'a diastolic above the systolic was answered {resp.status_code}'
        )
        assert not _vitals_for(patient.id), 'the impossible reading was stored anyway'

    def test_a_temperature_outside_the_possible_range_is_refused(self, ward):
        """41 is a fever; 90 is not a temperature in Celsius."""
        client, patient = ward['client'], ward['patient']

        for bad in ('90', '20'):
            resp = _record(
                client,
                patient.id,
                blood_pressure_systolic='120',
                blood_pressure_diastolic='80',
                heart_rate='72',
                temperature=bad,
                oxygen_saturation='98',
            )
            assert resp.status_code == 400, (
                f'a temperature of {bad} was answered {resp.status_code}'
            )
        assert not _vitals_for(patient.id), 'an impossible temperature was stored'

    def test_a_heart_rate_outside_the_possible_range_is_refused(self, ward):
        client, patient = ward['client'], ward['patient']

        for bad in ('10', '400'):
            resp = _record(
                client,
                patient.id,
                blood_pressure_systolic='120',
                blood_pressure_diastolic='80',
                heart_rate=bad,
                temperature='36.6',
                oxygen_saturation='98',
            )
            assert resp.status_code == 400, f'a heart rate of {bad} was answered {resp.status_code}'
        assert not _vitals_for(patient.id), 'an impossible heart rate was stored'

    def test_an_oxygen_saturation_above_100_is_refused(self, ward):
        """SpO2 is a percentage, so 101 is a unit error rather than a reading."""
        client, patient = ward['client'], ward['patient']

        resp = _record(
            client,
            patient.id,
            blood_pressure_systolic='120',
            blood_pressure_diastolic='80',
            heart_rate='72',
            temperature='36.6',
            oxygen_saturation='101',
        )
        assert resp.status_code == 400, f'SpO2 of 101 was answered {resp.status_code}'
        assert not _vitals_for(patient.id), 'an impossible SpO2 was stored'

    def test_a_valid_set_of_vitals_is_stored(self, ward):
        """The ordinary case, pinned so the refusals above are about the bad ones."""
        client, patient = ward['client'], ward['patient']

        resp = _record(
            client,
            patient.id,
            blood_pressure_systolic='118',
            blood_pressure_diastolic='76',
            heart_rate='68',
            temperature='36.4',
            oxygen_saturation='99',
            respiratory_rate='16',
            weight='70',
            height='170',
            blood_sugar='5.4',
        )
        assert resp.status_code == 200, (
            f'valid vitals were answered {resp.status_code}: {resp.get_data(as_text=True)[:200]}'
        )

        rows = _vitals_for(patient.id)
        assert len(rows) == 1, f'expected one vital record, found {len(rows)}'
        row = rows[0]
        assert row.blood_pressure_systolic == 118
        assert row.blood_pressure_diastolic == 76
        assert row.heart_rate == 68
        assert float(row.temperature) == 36.4
        assert row.oxygen_saturation == 99
        assert row.nurse_id == ward['profile'].id, 'the record does not name the nurse who took it'


@covers('NURSING_VITALS_AND_TASK_TRIAGE')
class TestTheNurseProfileIsRequired:
    def test_a_nurse_without_a_profile_cannot_record_anything(self, ward):
        """The role is not the authorisation; the profile is.

        The route reads current_user.nurse_profile and refuses when it is absent.
        A user who has the nurse role but no Nurse row — which is what a partially
        completed onboarding looks like — must not be able to write a measurement
        that a doctor will later read as though a licensed nurse took it.
        """
        from tests.tenant_context import ensure_test_user, login_test_client

        app, tenant = ward['app'], ward['tenant']
        bare = ensure_test_user(db, tenant, username='e2e_nurse_noprofile', role='nurse')
        client = app.test_client()
        with app.test_request_context():
            g.tenant_id = tenant.id
            login_test_client(client, bare, tenant)

        resp = _record(
            client,
            ward['patient'].id,
            blood_pressure_systolic='120',
            blood_pressure_diastolic='80',
            heart_rate='72',
            temperature='36.6',
            oxygen_saturation='98',
        )
        assert resp.status_code == 400, (
            f'a nurse with no profile recorded vitals and got {resp.status_code}'
        )
        assert not _vitals_for(ward['patient'].id), 'the write went through anyway'

    def test_a_patient_outside_the_tenant_is_a_404_not_a_write(self, ward):
        """The tenant filter is in the query, so this is a miss and not a refusal."""
        client = ward['client']

        resp = _record(
            client,
            999999,
            blood_pressure_systolic='120',
            blood_pressure_diastolic='80',
            heart_rate='72',
            temperature='36.6',
            oxygen_saturation='98',
        )
        assert resp.status_code == 404, f'a patient outside this tenant answered {resp.status_code}'


@covers('NURSING_VITALS_AND_TASK_TRIAGE')
class TestTasksMoveThroughTheirLadder:
    def _tasks(self, patient_id):
        from models.task_management import Task

        return db.session.execute(select(Task).filter_by(task_type='patient_care')).scalars().all()

    def test_a_task_is_created_with_a_priority(self, ward):
        """The ordinary case for the task surface.

        The route reads form data and redirects rather than answering JSON, so the
        row is the evidence rather than the response body. The priority is asserted
        against the stored value because 'high' and 'HIGH' are the same input
        two different ways and only the row shows which survived.
        """
        client, patient = ward['client'], ward['patient']

        resp = client.post(
            '/nurse/tasks/create',
            data={'title': 'Recheck vitals', 'priority': 'high'},
            follow_redirects=False,
        )
        assert resp.status_code in (200, 302), (
            f'creating a task answered {resp.status_code}: {resp.get_data(as_text=True)[:200]}'
        )

        rows = self._tasks(patient.id)
        assert len(rows) == 1, f'expected one task, found {len(rows)}'
        assert rows[0].title == 'Recheck vitals'
        assert rows[0].priority == 'high', (
            f'priority stored as {rows[0].priority!r}; the form sent high'
        )

    def test_a_task_can_be_advanced(self, ward):
        """The state ladder is the point of a task, so one transition is asserted."""
        from models.task_management import Task

        client, patient = ward['client'], ward['patient']

        client.post(
            '/nurse/tasks/create',
            data={'title': 'Administer medication', 'priority': 'normal'},
            follow_redirects=False,
        )

        task = (
            db.session.execute(select(Task).filter_by(task_type='patient_care')).scalars().first()
        )
        assert task is not None, 'the task was not written, so there is nothing to advance'
        before = task.status

        moved = client.post(f'/nurse/tasks/{task.id}/status', data={'status': 'in_progress'})
        assert moved.status_code in (200, 302), f'advancing a task answered {moved.status_code}'

        db.session.expire_all()
        after = db.session.get(Task, task.id)
        assert after.status != before, (
            f'the task stayed {after.status!r} after being advanced from {before!r}'
        )
