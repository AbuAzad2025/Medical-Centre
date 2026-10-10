"""Execute the radiology order-to-report lifecycle over real HTTP.

Phase 3c, second half. Radiology has the same shape as the laboratory: claim,
report, finalize. The same question applies and, as it turns out, the same defect
appears in a worse shape.

Driven through ``POST /radiology/worklist/complete/<id>`` and asserted on rows.

What execution established:

  * A real report finalizes correctly. Findings and impression are stored, the
    result goes VALIDATED, the request reaches DONE and the modality is inferred
    from the test name.

  * An empty POST finalizes it. ``action`` defaults to None when the form carries
    none, and None is treated as finalize, so posting nothing at all — which is
    what an abandoned or double-clicked form does — marks the report DONE and
    tells the doctor it is ready.

  * A draft save also tells the doctor it is ready. The notifier is called on
    every action, not only the finalizing one, so saving a work-in-progress report
    announces a finished one.
"""

from __future__ import annotations

import pytest
from flask import g
from sqlalchemy import select

from app.extensions import db
from models.radiology_request import RadiologyRequest
from models.radiology_result import RadiologyResult
from tests.scenario_execution_registry import covers


@pytest.fixture
def imaging(app, test_tenant):
    """A radiology technician and a request waiting to be reported."""
    from tests.tenant_context import activate_tenant_modules, ensure_test_user, login_test_client

    activate_tenant_modules(app, test_tenant, ['radiology'])
    user = ensure_test_user(db, test_tenant, username='e2e_rad_tech', role='radiology')
    client = app.test_client()
    with app.test_request_context():
        g.tenant_id = test_tenant.id
        login_test_client(client, user, test_tenant)

    from models.patient import Patient
    from models.visit import Visit

    patient = Patient(
        tenant_id=test_tenant.id,
        first_name='Rad',
        last_name='Patient',
        national_id='E2E-RAD-1',
    )
    db.session.add(patient)
    db.session.flush()
    visit = Visit(
        tenant_id=test_tenant.id,
        patient_id=patient.id,
        doctor_id=user.id,
        visit_number='E2E-RAD-VISIT-1',
        status='IN_PROGRESS',
    )
    db.session.add(visit)
    rad_request = RadiologyRequest(
        tenant_id=test_tenant.id,
        visit_id=visit.id,
        patient_id=patient.id,
        requested_by=user.id,
        # The model carries modality, not test_name. The route reads a form field
        # called test_name and infers modality from it, so the name is posted with
        # the report rather than stored on the request.
        modality='XRay',
        status='REQUESTED',
    )
    db.session.add(rad_request)
    db.session.commit()

    return {
        'app': app,
        'client': client,
        'tenant': test_tenant,
        'tech': user,
        'request': rad_request,
    }


def _report(client, request_id, action=None, **fields):
    """POST to the completion endpoint exactly as the worklist form does."""
    payload = dict(fields)
    if action is not None:
        payload['action'] = action
    return client.post(
        f'/radiology/worklist/complete/{request_id}',
        data=payload,
        follow_redirects=False,
    )


def _result_for(request_id):
    return (
        db.session.execute(select(RadiologyResult).filter_by(request_id=request_id))
        .scalars()
        .first()
    )


@covers('RADIOLOGY_ORDER_TO_REPORT')
class TestARealReportIsFinalizedCleanly:
    def test_a_report_with_findings_reaches_done(self, imaging):
        """The ordinary case, pinned so the failures below are about the empty one."""
        client, rad_request = imaging['client'], imaging['request']

        _report(
            client,
            rad_request.id,
            test_name='CT head',
            findings='No intracranial haemorrhage. No mass effect.',
            impression='Normal study',
        )

        from tests.tenant_context import refresh_scoped

        result = _result_for(rad_request.id)
        assert result is not None, 'no radiology result was written'
        assert result.findings and 'haemorrhage' in result.findings
        assert result.impression == 'Normal study'
        assert result.status == 'VALIDATED', f'result status is {result.status!r}'

        fresh = refresh_scoped(imaging['app'], imaging['tenant'], rad_request)
        assert fresh.status == 'DONE', f'request status is {fresh.status!r}'
        assert fresh.modality == 'CT', (
            f'modality is {fresh.modality!r}; "CT head" should have been recognised'
        )


@covers('RADIOLOGY_ORDER_TO_REPORT')
class TestFinalizeIsNotTheDefault:
    """What an empty or draft submission does to the report.

    Both fail, for the same underlying reason as the laboratory module: the
    finalize decision is taken from the absence of an action rather than from the
    presence of a report.
    """

    @pytest.mark.xfail(
        strict=True,
        reason=(
            'known defect: an empty POST carries no action, and a missing action is '
            'treated as finalize, so posting nothing marks the report DONE'
        ),
    )
    def test_an_empty_submission_does_not_finalize_the_report(self, imaging):
        """A form nobody filled in is not a report.

        This is what an abandoned draft, a double-clicked submit and a client that
        posts an empty body all produce. None of them is a radiology opinion.
        """
        client, rad_request = imaging['client'], imaging['request']

        _report(client, rad_request.id)

        from tests.tenant_context import refresh_scoped

        fresh = refresh_scoped(imaging['app'], imaging['tenant'], rad_request)
        result = _result_for(rad_request.id)
        has_content = bool((result and (result.findings or result.impression)) or '')
        assert not (fresh.status == 'DONE' and not has_content), (
            f'an empty submission marked request {rad_request.id} DONE with no findings '
            f'and no impression. action defaults to None and None counts as finalize, '
            f'so the report is declared complete before anybody wrote one.'
        )

    @pytest.mark.xfail(
        strict=True,
        reason=(
            'known defect: _notify_radiology_complete is called on every action, so '
            'saving a draft announces a finished report to the requester'
        ),
    )
    def test_a_draft_save_does_not_announce_a_finished_report(self, imaging):
        """Saving work in progress is not completing it.

        The request stays IN_PROGRESS here, so the state is honest; only the
        notification is not. That combination is the worst of both, because the
        worklist shows a request still open while the doctor has been told to read
        it.
        """
        from models.notification import Notification

        client, rad_request = imaging['client'], imaging['request']

        _report(
            client,
            rad_request.id,
            action='save',
            findings='partial: no acute bleed on the first series',
        )

        sent = (
            db.session.execute(
                select(Notification).filter(
                    Notification.recipient_id == imaging['tech'].id,
                    Notification.title.like('%الأشعة%'),
                )
            )
            .scalars()
            .all()
        )
        assert not sent, (
            f'{len(sent)} notification(s) announced a finished report for a draft '
            f'save. _notify_radiology_complete runs after every action rather than '
            f'only when should_finalize is true.'
        )
