"""Execute the emergency intake-to-resolution lifecycle over real HTTP.

Phase 3e. An emergency case is born, triaged, treated, and either resolved or
converted to an inpatient/lab/radiology pathway. The specification is a state
machine (WAITING -> TRIAGE -> TREATMENT -> COMPLETED/TRANSFERRED) so it is
worth asking what the application actually does when the status moves.

Driven through ``POST /emergency/cases/create``, ``POST /emergency/cases/<id>/resolve``,
and ``POST /emergency/cases/<id>/convert`` and asserted on rows.

What execution established:

  * A case is created with WAITING status, a visit is opened, and an
    EmergencyStatusHistory row records the transition from null to WAITING.

  * Resolving a case sets COMPLETED and stamps completed_at, and the history
    records the transition. The resolved case still carries its severity,
    vitals and notes.

  * Converting an emergency to inpatient/lab/radiology transfers the visit
    via the queue service, BUT the emergency case itself is NOT updated — its
    status stays WAITING (or whatever it was) and no history row is written
    for the conversion. The case and the visit drift apart.

  * The case_number uses second-granularity timestamp against a unique column.
    Two rapid creates on the same patient collide and the second fails with
    IntegrityError, leaving the session in PendingRollbackError. This is the
    same defect shape as the prescription number.
"""

from __future__ import annotations

import uuid

import pytest
from flask import g
from sqlalchemy import select

from app.extensions import db
from models.emergency import EmergencyCase
from models.emergency_status_history import EmergencyStatusHistory
from models.visit import Visit
from tests.scenario_execution_registry import covers


@pytest.fixture
def er(app, test_tenant):
    """An emergency clinician and a patient."""
    from tests.tenant_context import activate_tenant_modules, ensure_test_user, login_test_client

    activate_tenant_modules(app, test_tenant, ['emergency'])
    user = ensure_test_user(db, test_tenant, username='e2e_er_doc', role='emergency')
    client = app.test_client()
    with app.test_request_context():
        g.tenant_id = test_tenant.id
        login_test_client(client, user, test_tenant)

    from models.patient import Patient

    patient = Patient(
        tenant_id=test_tenant.id,
        first_name='Er',
        last_name='Patient',
        national_id='E2E-ER-1',
    )
    db.session.add(patient)
    db.session.commit()

    # convert_emergency_case resolves a target department by matching
    # Department.get_type() against the department's NAME - the table has no
    # type column. Without these rows the route answers 404 "department not
    # found" before it ever reaches the transfer, so the case-status assertions
    # below could never be reached. Seeded inside the tenant's RLS scope:
    # departments carries a WITH CHECK policy.
    from models.department import Department
    from tests.tenant_context import create_scoped

    tag = uuid.uuid4().hex[:6]
    doctor = ensure_test_user(db, test_tenant, username=f'e2e_er_doc_{tag}', role='doctor')
    emergency_dept = create_scoped(
        app,
        test_tenant,
        Department(
            tenant_id=test_tenant.id,
            name=f'Emergency-{tag}',
            name_ar=f'OUUU>-{tag}',
            is_active=True,
            location='ER 1',
        ),
    )
    lab_dept = create_scoped(
        app,
        test_tenant,
        Department(
            tenant_id=test_tenant.id,
            name=f'Lab-{tag}',
            name_ar=f'O?O?-{tag}',
            is_active=True,
            location='Lab 1',
        ),
    )
    general_dept = create_scoped(
        app,
        test_tenant,
        Department(
            tenant_id=test_tenant.id,
            name=f'General-{tag}',
            name_ar=f'O>?U>-{tag}',
            is_active=True,
            location='Ward 1',
        ),
    )

    return {
        'app': app,
        'client': client,
        'tenant': test_tenant,
        'doctor': user,
        'ward_doctor': doctor,
        'patient': patient,
        'emergency_dept': emergency_dept,
        'lab_dept': lab_dept,
        'general_dept': general_dept,
    }


def _create_case(client, patient_id, **overrides):
    """POST the create endpoint exactly as the caller does."""
    payload = {
        'patient_id': str(patient_id),
        'case_description': 'chest pain',
        'priority': 'HIGH',
    }
    payload.update(overrides)
    return client.post(
        '/emergency/cases/create',
        json=payload,
        follow_redirects=False,
    )


def _resolve_case(client, case_id):
    return client.post(
        f'/emergency/cases/{case_id}/resolve',
        follow_redirects=False,
    )


def _convert_case(client, case_id, destination):
    return client.post(
        f'/emergency/cases/{case_id}/convert',
        json={'new_destination': destination},
        follow_redirects=False,
    )


def _fresh(app, tenant, obj):
    from tests.tenant_context import refresh_scoped

    return refresh_scoped(app, tenant, obj)


@covers('EMERGENCY_TRIAGE_TREATMENT_RESOLUTION')
class TestCaseIsCreatedCorrectly:
    """The write itself: a case, a visit, and the first history row."""

    def test_an_emergency_case_lands_with_waiting_and_a_history_row(self, er):
        """The create endpoint writes the case, the visit, and the initial history."""
        client, patient = er['client'], er['patient']

        resp = _create_case(client, patient.id)
        assert resp.status_code == 200, f'create answered {resp.status_code}'
        body = resp.get_json()
        assert body.get('success') is True, f'create reported {body!r}'

        case_id = body['case_id']
        case = db.session.get(EmergencyCase, case_id)
        assert case is not None, 'the case was not written'
        assert case.patient_id == er['patient'].id
        assert case.status == 'WAITING', f'status is {case.status!r}'
        assert case.chief_complaint == 'chest pain'

        # The visit is created and marked emergency.
        visit = db.session.get(Visit, case.visit_id)
        assert visit is not None, 'the visit was not created'
        assert visit.is_emergency is True
        assert visit.visit_type == 'EMERGENCY'

        # The initial history row: null -> WAITING.
        history = (
            db.session.execute(select(EmergencyStatusHistory).filter_by(emergency_id=case.id))
            .scalars()
            .all()
        )
        assert len(history) == 1, f'expected one history row, found {len(history)}'
        assert history[0].from_status is None
        assert history[0].to_status == 'WAITING'


@covers('EMERGENCY_TRIAGE_TREATMENT_RESOLUTION')
class TestResolutionIsRecorded:
    """Resolving a case stamps COMPLETED and records the transition."""

    def test_resolving_a_case_stamps_completed_and_writes_history(self, er):
        client, patient = er['client'], er['patient']

        resp = _create_case(client, patient.id)
        case_id = resp.get_json()['case_id']

        _resolve_case(client, case_id)

        fresh = _fresh(er['app'], er['tenant'], db.session.get(EmergencyCase, case_id))
        assert fresh.status == 'COMPLETED', f'status is {fresh.status!r}'
        assert fresh.completed_at is not None, 'completed_at was not stamped'

        history = (
            db.session.execute(
                select(EmergencyStatusHistory)
                .filter_by(emergency_id=case_id)
                .order_by(EmergencyStatusHistory.created_at)
            )
            .scalars()
            .all()
        )
        assert len(history) == 2, (
            f'expected two history rows (WAITING + COMPLETED), found {len(history)}'
        )
        assert history[1].from_status == 'WAITING'
        assert history[1].to_status == 'COMPLETED'


@covers('EMERGENCY_TRIAGE_TREATMENT_RESOLUTION')
class TestTheCaseAndVisitDriftOnConvert:
    """Converting an emergency transfers the visit but leaves the case behind."""

    def test_converting_to_lab_updates_the_case_status(self, er):
        """A conversion to lab should move the case to TRANSFERRED and write history."""
        from models.emergency_status_history import EmergencyStatusHistory

        client, patient = er['client'], er['patient']

        resp = _create_case(client, patient.id)
        case_id = resp.get_json()['case_id']

        _convert_case(client, case_id, 'lab')

        fresh = _fresh(er['app'], er['tenant'], db.session.get(EmergencyCase, case_id))
        assert fresh.status == 'TRANSFERRED', (
            f'the emergency case still says {fresh.status!r} after conversion; '
            'the visit was transferred but the case was not updated'
        )

        history = (
            db.session.execute(
                select(EmergencyStatusHistory)
                .filter_by(emergency_id=case_id)
                .order_by(EmergencyStatusHistory.created_at)
            )
            .scalars()
            .all()
        )
        assert any(h.to_status == 'TRANSFERRED' for h in history), (
            'no history row records the transfer; the case and the visit drift apart'
        )

    def test_converting_to_inpatient_updates_the_case_status(self, er):
        """A conversion to inpatient (doctor) should move the case to TRANSFERRED."""
        from models.emergency_status_history import EmergencyStatusHistory

        client, patient = er['client'], er['patient']

        resp = _create_case(client, patient.id)
        case_id = resp.get_json()['case_id']

        _convert_case(client, case_id, 'doctor')

        fresh = _fresh(er['app'], er['tenant'], db.session.get(EmergencyCase, case_id))
        assert fresh.status == 'TRANSFERRED', (
            f'the emergency case still says {fresh.status!r} after inpatient conversion'
        )

        history = (
            db.session.execute(
                select(EmergencyStatusHistory)
                .filter_by(emergency_id=case_id)
                .order_by(EmergencyStatusHistory.created_at)
            )
            .scalars()
            .all()
        )
        assert any(h.to_status == 'TRANSFERRED' for h in history), (
            'no history row records the inpatient transfer'
        )


@covers('EMERGENCY_TRIAGE_TREATMENT_RESOLUTION')
class TestCaseNumberIsUniquePerVisit:
    """The case_number includes the visit_id, so each create gets a unique number."""

    def test_each_create_gets_a_unique_case_number(self, er):
        """Each emergency create generates a new visit and thus a unique case_number."""
        client, patient = er['client'], er['patient']

        _create_case(client, patient.id)
        first = (
            db.session.execute(select(EmergencyCase).filter_by(patient_id=patient.id))
            .scalars()
            .all()
        )
        assert len(first) == 1

        _create_case(client, patient.id)
        second = (
            db.session.execute(select(EmergencyCase).filter_by(patient_id=patient.id))
            .scalars()
            .all()
        )

        assert len(second) == 2, (
            f'the second create was refused: the patient has {len(second)} case(s)'
        )
        assert first[0].case_number != second[1].case_number, (
            'both cases got the same case_number; they should differ because each '
            'create opens a new visit with a new id'
        )
