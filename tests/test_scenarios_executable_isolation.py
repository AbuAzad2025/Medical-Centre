"""Execute the queue lifecycle and the tenant boundary.

Layer 2, final group. Two things that are easy to claim and hard to be sure of:

  Queue  skip, return and emergency-debt approval. The queue is where a patient
         physically waits, so the property that matters is that a ticket cannot
         silently disappear or duplicate. Emergency debt is the documented way an
         unpaid patient is admitted anyway, which is the one case where the payment
         gate is deliberately bypassed, and a bypass with no assertion is a bypass
         nobody has checked.

  Tenant a row written in one tenant must not be readable from another. This is
         asserted over HTTP with two real tenants rather than by reading the
         middleware, because the middleware is exactly the layer that has been
         wrong before: the coverage gates were under-reporting because a fixture
         read the wrong corpus, and the tenant exemption list grew a diagnostic
         route nobody reviewed.

Falsifiable, like the rest: if a boundary stops holding, the test names the layer
that changed rather than reporting a generic failure.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from flask import g
from sqlalchemy import select

from app.extensions import db
from models.queue_management import QueueManagement
from models.visit import Visit
from tests.test_scenarios_executable import (
    _accountant,
    _create_visit_http,
    _department,
    _doctor,
    _latest_visit_for,
    _patient,
    _service,
)


def _reception_client(app, tenant, username='e2e_queue_reception'):
    from tests.tenant_context import ensure_test_user, login_test_client

    user = ensure_test_user(db, tenant, username=username, role='reception')
    client = app.test_client()
    login_test_client(client, user, tenant)
    return client, user


def _paid_visit(
    app, client, tenant, dept, doctor, service, login_as, username='e2e_queue_reception'
):
    """A visit, paid in full, with a live queue ticket.

    The visit is opened as a receptionist and paid as an accountant, because the
    two routes are gated to different roles and that handoff is part of what is
    under test. The ticket needs a doctor because the queue gate requires one for a
    department whose type is general, which is what the ad-hoc department here is.

    Paying first is not incidental: the queue refuses an unpaid patient, so a queue
    test that skipped payment would be testing the refusal and calling it a
    lifecycle.
    """
    from tests.tenant_context import ensure_test_user, login_test_client

    receptionist = ensure_test_user(db, tenant, username=username, role='reception')
    desk = app.test_client()

    accountant = ensure_test_user(db, tenant, username='e2e_queue_payer', role='accountant')
    paying = app.test_client()

    patient = _patient(app, tenant.id)
    # The session is minted inside the request context and with the password the
    # helper seeded, which is what the cash spine does. Logging in outside the
    # context leaves the request without the tenant binding it expects, and the
    # payment comes back 403 rather than being refused for a role reason.
    with app.test_request_context():
        g.tenant_id = tenant.id
        login_test_client(desk, receptionist, tenant)
        resp = _create_visit_http(
            desk, app, patient, dept, doctor, selected_tests=[str(service.id)]
        )
    assert resp.status_code in (200, 302), f'visit creation returned {resp.status_code}'

    visit = _latest_visit_for(app, patient.id)
    assert visit is not None, 'no visit row was created by the reception endpoint'
    assert Decimal(str(visit.total_amount)) > 0, 'the visit priced at zero'

    with app.test_request_context():
        g.tenant_id = tenant.id
        login_test_client(paying, accountant, tenant)
        paid = paying.post(
            f'/payment/process/{visit.id}',
            data={
                'payment_method': 'cash',
                'paid_amount': str(visit.total_amount),
                'payment_reference': f'queue-{visit.id}',
            },
            follow_redirects=False,
        )
    assert paid.status_code in (200, 302), f'the payment was not accepted: {paid.status_code}'

    with app.test_request_context():
        g.tenant_id = tenant.id
        login_test_client(desk, receptionist, tenant)
        desk.post(
            '/reception/queue/add-patient',
            data={
                'visit_id': visit.id,
                'patient_id': patient.id,
                'department_id': dept.id,
                'doctor_id': doctor.id,
            },
            follow_redirects=False,
        )
    login_as(client, username, 'reception')
    return visit, patient


def _tickets_for(app, visit_id):
    return (
        db.session.execute(
            select(QueueManagement).filter_by(visit_id=visit_id).order_by(QueueManagement.id)
        )
        .scalars()
        .all()
    )


@pytest.fixture
def queueing(app, client, login_as, test_tenant):
    """A reception client with a department, a doctor and a priced service."""
    dept = _department(app)
    doctor = _doctor(app, test_tenant)
    service = _service(app, test_tenant, dept)
    _accountant(app, test_tenant)
    return {
        'app': app,
        'client': client,
        'tenant': test_tenant,
        'dept': dept,
        'doctor': doctor,
        'service': service,
        'login_as': login_as,
    }


class TestQueueLifecycleIsExecuted:
    """A ticket can be skipped and returned without duplicating or vanishing."""

    def test_skip_then_return_leaves_exactly_one_live_ticket(self, queueing):
        """The pair of routes that could plausibly double a patient is exercised.

        skip marks a ticket skipped and return puts it back into the queue. If
        return created a new row instead of reviving the old one, a patient would
        appear twice on the waiting board, which is the specific failure these two
        routes exist to prevent.
        """
        app, client, tenant = queueing['app'], queueing['client'], queueing['tenant']
        visit, _patient_row = _paid_visit(
            app,
            client,
            tenant,
            queueing['dept'],
            queueing['doctor'],
            queueing['service'],
            queueing['login_as'],
        )
        before = _tickets_for(app, visit.id)
        assert len(before) == 1, (
            f'a paid visit produced {len(before)} queue tickets before the lifecycle '
            f'even started; the add-patient route is not idempotent'
        )
        ticket = before[0]

        with app.test_request_context():
            g.tenant_id = tenant.id
            client.post(
                f'/reception/queue/skip-patient/{ticket.id}',
                data={'reason': 'patient stepped away'},
                follow_redirects=False,
            )
        db.session.expire_all()
        skipped = _tickets_for(app, visit.id)
        assert len(skipped) == 1, (
            f'skipping produced {len(skipped)} tickets; the skip created a row rather '
            f'than moving the existing one'
        )
        assert skipped[0].status.lower() == 'skipped', (
            f'the ticket reads {skipped[0].status!r} after a skip. QueueState stores this '
            f'lowercase while PaymentStatus stores uppercase, so the comparison is '
            f'case-folded rather than assuming one convention across the two enums'
        )

        with app.test_request_context():
            g.tenant_id = tenant.id
            client.post(
                f'/reception/queue/return-to-queue/{ticket.id}',
                data={'reason': 'patient is back'},
                follow_redirects=False,
            )
        db.session.expire_all()
        returned = _tickets_for(app, visit.id)
        assert len(returned) == 1, (
            f'returning produced {len(returned)} tickets; return-to-queue created a '
            f'second row, so this patient is now on the board twice'
        )
        assert returned[0].status.lower() != 'skipped', (
            f'the ticket is still {returned[0].status!r} after a return; the status was not moved'
        )

    def test_emergency_debt_approval_is_unreachable_for_an_unpaid_visit(self, queueing):
        """The documented bypass of the payment gate cannot actually be used.

        Emergency debt approval takes a ticket id and sets the visit to EMERGENCY_DEBT.
        A ticket only exists if the queue admitted the patient, and the queue admits
        only a PAID visit, so the route is asked to approve a ticket the gate makes
        impossible to create.

        `force_entry` used to be the way in and it was removed: add_patient_to_queue no
        longer takes it, so nothing else creates a ticket for an unpaid patient. The
        bypass is therefore dead code, which means an unpaid emergency patient has no
        route through the queue at all.

        Asserted as the finding it is. When the route becomes reachable this test fails,
        which is the moment the note should be rewritten.
        """
        app, tenant = queueing['app'], queueing['tenant']
        from tests.tenant_context import ensure_test_user, login_test_client

        desk = app.test_client()
        receptionist = ensure_test_user(db, tenant, username='e2e_debt_reception', role='reception')
        patient = _patient(app, tenant.id)
        with app.test_request_context():
            g.tenant_id = tenant.id
            login_test_client(desk, receptionist, tenant)
            _create_visit_http(
                desk,
                app,
                patient,
                queueing['dept'],
                queueing['doctor'],
                selected_tests=[str(queueing['service'].id)],
            )
        visit = _latest_visit_for(app, patient.id)
        assert visit is not None, 'no visit row was created by the reception endpoint'
        assert visit.payment_status == 'PENDING', (
            f'the visit is {visit.payment_status}; this test needs it unpaid and the '
            f'gate is being asserted elsewhere'
        )

        # The queue refuses it, which is the invariant the bypass exists to override.
        with app.test_request_context():
            g.tenant_id = tenant.id
            desk.post(
                '/reception/queue/add-patient',
                data={
                    'visit_id': visit.id,
                    'patient_id': patient.id,
                    'department_id': queueing['dept'].id,
                    'doctor_id': queueing['doctor'].id,
                },
                follow_redirects=False,
            )
        assert not _tickets_for(app, visit.id), (
            'an unpaid visit entered the queue; the payment gate is not enforcing'
        )

        # Approve the debt. The ticket does not exist, because the queue refused it,
        # so the approval is attempted against the visit the way the desk would.
        with app.test_request_context():
            g.tenant_id = tenant.id
            approval = desk.post(
                f'/reception/queue/approve-emergency-debt/{visit.id}',
                data={'max_amount': '100'},
                follow_redirects=False,
            )
        db.session.expire_all()
        refreshed = db.session.get(Visit, visit.id)
        assert refreshed.payment_status == 'PENDING', (
            f'an unpaid visit now reaches {refreshed.payment_status} through the '
            f'emergency-debt route (HTTP {approval.status_code}); the bypass has become '
            f'reachable, so the documented finding is stale and this test should be '
            f'rewritten to assert the visit being admitted'
        )
        assert not _tickets_for(app, visit.id), (
            f'an unpaid visit gained a queue ticket with {approval.status_code}; the '
            f'payment gate is no longer refusing, and emergency debt is not the reason'
        )


class TestTenantIsolationIsExecuted:
    """A row written in one tenant is not reachable from another, over HTTP.

    Two real tenants, two real patients, and the request made from one session
    against the other's id. Both halves are asserted: the refusal, and the fact
    that the row is still there afterwards. A refused request that also destroyed
    the row would satisfy a refusal-only check.
    """

    def test_a_visit_from_one_tenant_is_not_visible_from_another(
        self, app, client, test_tenant, login_as
    ):
        from app.core.tenant.models import Tenant
        from tests.tenant_context import ensure_test_user

        home_dept = _department(app)
        home_doctor = _doctor(app, test_tenant)
        home_service = _service(app, test_tenant, home_dept)
        home_client = client
        visit, _patient_row = _paid_visit(
            app, home_client, test_tenant, home_dept, home_doctor, home_service, login_as
        )

        # A second tenant, with its own clinician, created rather than assumed.
        other = Tenant(
            name='isolation-probe',
            name_ar='probe',
            slug='isolation-probe',
            # contact_email is NOT NULL on the tenants table, so the probe tenant is
            # built to satisfy the same constraints a real tenant would.
            contact_email='probe@example.invalid',
            contact_phone='0500000000',
            status='active',
        )
        db.session.add(other)
        db.session.commit()

        stranger = ensure_test_user(db, other, username='e2e_stranger', role='reception')
        stranger_client = app.test_client()
        from tests.tenant_context import login_test_client

        login_test_client(stranger_client, stranger, other)

        resp = stranger_client.get(f'/reception/view_visit/{visit.id}', follow_redirects=False)
        assert resp.status_code in (302, 403, 404), (
            f'tenant {other.id} read visit {visit.id} from tenant {test_tenant.id} with '
            f'{resp.status_code}; the tenant boundary is not holding'
        )

        body = resp.get_data(as_text=True)
        assert (
            str(visit.id) not in body
            or 'not found' in body.lower()
            or resp.status_code
            in (
                403,
                404,
            )
        ), (
            'the cross-tenant read returned a body containing the other tenant visit id '
            f'with status {resp.status_code}'
        )

        # And the row is untouched: a refused read must not have consumed it.
        db.session.expire_all()
        survivor = db.session.get(Visit, visit.id)
        assert survivor is not None, (
            f'visit {visit.id} disappeared after a refused cross-tenant read; the '
            f'refusal destroyed a row it was supposed to protect'
        )
        assert survivor.tenant_id == test_tenant.id, (
            'the visit changed tenant; a refused read wrote to it'
        )

    def test_the_diagnostic_route_still_answers_without_a_session(self, app):
        """/_ghost_whoami remains unauthenticated, which is the recorded finding.

        Duplicated from the access-control file on purpose rather than imported: the
        two files assert it for different reasons, and a single place to change a
        security finding is a single place for it to be quietly changed.
        """
        resp = app.test_client().get('/_ghost_whoami', follow_redirects=False)
        assert resp.status_code == 200, (
            '/_ghost_whoami now answers anonymously; the documented finding is stale and '
            'this test should be rewritten to assert the refusal'
        )
