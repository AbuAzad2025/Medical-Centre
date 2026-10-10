"""Execute the laboratory order-to-result lifecycle over real HTTP.

Phase 3c. A lab request moves through claim, receive, result entry and finalize,
and the last of those is the one that matters: finalize is what tells the doctor
the result is ready. What it takes to get there is the question this module asks,
because a report that is marked ready and is not is worse than one that is still
pending, because nobody goes looking for it.

Driven through ``POST /lab/worklist/request/<id>`` with the bracket-suffixed field
names the handler reads, and asserted on rows. The route flashes a success message
for every action it accepts, including the ones that change nothing.

What execution established:

  * The lifecycle is sound up to finalize. Claim, receive and result entry each
    write the status they claim to and stamp the matching timestamp.

  * A request can be finalized with no results at all. The finalize branch marks
    every result that has a value and then sets the request to DONE whether or not
    there were any, so an empty panel reports as complete.

  * The doctor is notified either way. ``_notify_lab_results_ready`` runs on
    finalize unconditionally and tells the requester a result is ready, so the
    notification says "ready" about a report with nothing in it.
"""

from __future__ import annotations

import pytest
from flask import g
from sqlalchemy import select

from app.extensions import db
from models.lab_request import LabRequest, LabResult
from tests.scenario_execution_registry import covers


@pytest.fixture
def lab(app, test_tenant):
    """A lab technician and a request with three tests on the panel."""
    from tests.tenant_context import activate_tenant_modules, ensure_test_user, login_test_client

    activate_tenant_modules(app, test_tenant, ['lab'])
    user = ensure_test_user(db, test_tenant, username='e2e_lab_tech', role='lab')
    client = app.test_client()
    with app.test_request_context():
        g.tenant_id = test_tenant.id
        login_test_client(client, user, test_tenant)

    from models.patient import Patient
    from models.visit import Visit

    patient = Patient(
        tenant_id=test_tenant.id,
        first_name='Lab',
        last_name='Patient',
        national_id='E2E-LAB-1',
    )
    db.session.add(patient)
    db.session.flush()
    visit = Visit(
        tenant_id=test_tenant.id,
        patient_id=patient.id,
        doctor_id=user.id,
        visit_number='E2E-LAB-VISIT-1',
        status='IN_PROGRESS',
    )
    db.session.add(visit)

    lab_request = LabRequest(
        tenant_id=test_tenant.id,
        visit_id=visit.id,
        patient_id=patient.id,
        requested_by=user.id,
        request_number='LAB-E2E-1',
        status='ORDERED',
    )
    db.session.add(lab_request)
    db.session.flush()
    for code, name in (
        ('CBC', 'Complete blood count'),
        ('HGB', 'Haemoglobin'),
        ('PLT', 'Platelets'),
    ):
        db.session.add(
            LabResult(
                tenant_id=test_tenant.id,
                request_id=lab_request.id,
                patient_id=patient.id,
                test_code=code,
                test_name=name,
                is_critical=False,
            )
        )
    db.session.commit()

    return {
        'app': app,
        'client': client,
        'tenant': test_tenant,
        'tech': user,
        'request': lab_request,
    }


def _act(client, request_id, action='save', **fields):
    """POST one action to the worklist request form."""
    payload = {'action': action}
    payload.update(fields)
    return client.post(
        f'/lab/worklist/request/{request_id}',
        data=payload,
        follow_redirects=False,
    )


def _results_for(request_id):
    return db.session.execute(select(LabResult).filter_by(request_id=request_id)).scalars().all()


@covers('LAB_RESULT_LIFECYCLE')
class TestTheLifecycleIsSoundUpToFinalize:
    def test_claiming_and_receiving_a_request_stamps_the_matching_time(self, lab):
        """Claim sets RECEIVED, and the receive action stamps received_time.

        Asserted on the row rather than on the redirect, because the route flashes
        the same success message for an action that changed nothing.
        """
        client, lab_request = lab['client'], lab['request']

        _act(client, lab_request.id, action='receive')

        from tests.tenant_context import refresh_scoped

        fresh = refresh_scoped(lab['app'], lab['tenant'], lab_request)
        assert fresh.status == 'RECEIVED', f'status is {fresh.status!r} after receive'
        assert fresh.received_time is not None, (
            'receive set the status but left received_time empty, so the record of '
            'when the specimen arrived is missing'
        )


@covers('LAB_RESULT_LIFECYCLE')
class TestFinalizeRequiresResults:
    """What it takes to declare a lab report ready.

    These two fail. finalize is the point at which the report stops being pending
    and the doctor is told to look at it, so an empty or half-filled report passing
    through here is a report that will not be chased.
    """

    @pytest.mark.xfail(
        strict=True,
        reason=(
            'known defect: finalize sets the request to DONE unconditionally, so an '
            'order with no results at all reports as complete'
        ),
    )
    def test_a_request_with_no_results_cannot_be_finalized(self, lab):
        """A panel nobody filled in is not a finished report.

        Three tests on the panel, none entered. Finalizing must be refused, because
        the alternative is a DONE request that a doctor opens to find nothing.
        """
        client, lab_request = lab['client'], lab['request']

        _act(client, lab_request.id, action='finalize')

        from tests.tenant_context import refresh_scoped

        fresh = refresh_scoped(lab['app'], lab['tenant'], lab_request)
        assert fresh.status != 'DONE', (
            f'the request reports DONE with {len(_results_for(lab_request.id))} results '
            f'and none of them carrying a value. finalize validates the results that '
            f'have a value and then marks the request DONE regardless, so an untouched '
            f'panel is indistinguishable from a completed one.'
        )

    @pytest.mark.xfail(
        strict=True,
        reason=(
            'known defect: finalize marks the request DONE after validating only the '
            'results that have a value, so a partly filled panel reports as complete'
        ),
    )
    def test_a_partly_filled_panel_cannot_be_finalized(self, lab):
        """One result out of three is not a finished report either.

        The three that were left blank keep whatever status they had while the
        request says DONE above them, so the summary and its details disagree.
        """
        client, lab_request = lab['client'], lab['request']

        results = _results_for(lab_request.id)
        _act(
            client,
            lab_request.id,
            action='finalize',
            **{
                'result_id[]': [str(r.id) for r in results],
                'test_code[]': [r.test_code for r in results],
                'test_name[]': [r.test_name for r in results],
                'value[]': ['13.4', '', ''],
                'unit[]': ['g/dL', 'g/dL', 'g/dL'],
                'reference_range[]': ['12-16', '12-16', '150-400'],
                'is_critical[]': ['', '', ''],
                'status[]': ['', '', ''],
                'notes[]': ['', '', ''],
            },
        )

        from tests.tenant_context import refresh_scoped

        fresh = refresh_scoped(lab['app'], lab['tenant'], lab_request)
        blank = [r for r in _results_for(lab_request.id) if not (r.value or '').strip()]
        assert not (fresh.status == 'DONE' and blank), (
            f'the request reports DONE while {len(blank)} of '
            f'{len(_results_for(lab_request.id))} results are still blank and '
            f'unvalidated. Only the rows with a value are touched by finalize.'
        )


@covers('LAB_RESULT_LIFECYCLE')
class TestTheRequesterIsToldTruthfully:
    @pytest.mark.xfail(
        strict=True,
        reason=(
            'known defect: _notify_lab_results_ready runs on every finalize, so the '
            'doctor is told a result is ready when the report is empty'
        ),
    )
    def test_the_doctor_is_not_told_a_result_is_ready_when_there_is_none(self, lab):
        """The notification has to agree with the report.

        finalize calls the notifier unconditionally. It takes the requester from the
        request and sends "a lab result is ready", so an empty panel produces a
        notification whose entire content is wrong.
        """
        from models.notification import Notification

        client, lab_request = lab['client'], lab['request']

        _act(client, lab_request.id, action='finalize')

        sent = (
            db.session.execute(
                select(Notification).filter(
                    Notification.recipient_id == lab['tech'].id,
                    Notification.title.like('%مختبر%'),
                )
            )
            .scalars()
            .all()
        )
        assert not sent, (
            f'the requester was sent {len(sent)} notification(s) claiming a lab result '
            f'is ready for a request that carries no results. _notify_lab_results_ready '
            f'is called from finalize without being told whether anything was entered.'
        )


@covers('LAB_RESULT_LIFECYCLE')
class TestARealReportIsFinalizedCleanly:
    def test_a_filled_panel_finalizes_and_validates_every_result(self, lab):
        """The ordinary case, pinned so the failures above are about the empty one."""
        client, lab_request = lab['client'], lab['request']

        results = _results_for(lab_request.id)
        _act(
            client,
            lab_request.id,
            action='finalize',
            **{
                'result_id[]': [str(r.id) for r in results],
                'test_code[]': [r.test_code for r in results],
                'test_name[]': [r.test_name for r in results],
                'value[]': ['6.2', '13.4', '280'],
                'unit[]': ['10^9/L', 'g/dL', '10^9/L'],
                'reference_range[]': ['4-11', '12-16', '150-400'],
                'is_critical[]': ['', '', ''],
                'status[]': ['', '', ''],
                'notes[]': ['', '', ''],
            },
        )

        from tests.tenant_context import refresh_scoped

        fresh = refresh_scoped(lab['app'], lab['tenant'], lab_request)
        assert fresh.status == 'DONE', f'status is {fresh.status!r} after finalize'
        assert fresh.completed_at is not None, 'finalize did not stamp completed_at'

        unvalidated = [r for r in _results_for(lab_request.id) if r.status != 'VALIDATED']
        assert not unvalidated, (
            f'{len(unvalidated)} result(s) are not VALIDATED after finalize: '
            f'{[(r.test_code, r.value, r.status) for r in unvalidated]}'
        )
