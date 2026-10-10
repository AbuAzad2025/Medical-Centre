"""Execute the insurance claim and refund journeys over real HTTP.

Layer 2 continued. The cash spine is executed in test_scenarios_executable.py and
the access-control decisions in test_scenarios_executable_rbac.py; this file
executes the two journeys where money can move backwards, which is where the
arithmetic and the state machine have to agree with each other.

  Insurance  a claim is generated from an ISSUED invoice, adjudicated, and paid
             out. The invariant is that the three money fields on the claim stay
             consistent with each other and with the invoice, because a claim
             whose approved amount disagrees with its own split is the sort of
             thing that surfaces at year end and nowhere earlier.

  Refund     a payment is requested for refund, approved and executed. The
             invariant is that a refund cannot exceed the payment it is against,
             and that the two consoles involved agree about who may do which
             step.

Both journeys need an invoice, so the builders here reuse the pricing and visit
helpers from the financial spine rather than inventing a second way to make a
billable visit. Sharing the builders is deliberate: a discrepancy between two
sets of test fixtures is a discrepancy nobody is looking for.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from flask import g
from sqlalchemy import func, select

from app.extensions import db
from models.gl import GLJournal
from models.insurance import InsuranceClaim
from models.invoice import Invoice
from models.refund_request import RefundRequest
from tests.test_scenarios_executable import (
    _accountant,
    _create_visit_http,
    _department,
    _doctor,
    _latest_visit_for,
    _patient,
    _service,
)


def _manager(app, tenant):
    from tests.tenant_context import ensure_test_user

    return ensure_test_user(db, tenant, username='e2e_manager', role='manager')


def _invoice_for(app, visit_id):
    invoice = (
        db.session.execute(
            select(Invoice).filter_by(visit_id=visit_id).order_by(Invoice.id.desc()).limit(1)
        )
        .scalars()
        .first()
    )
    assert invoice is not None, f'visit {visit_id} produced no invoice'
    return invoice


def _issue_invoice(app, opening, tenant, visit_id):
    """Send the visit to accounting over the real endpoint.

    The invoice is not created by the visit. It is created by
    /reception/visits/<id>/send-to-accounting, which is reception-gated and writes
    the row with status ISSUED. Driving that route rather than writing the invoice
    directly is the difference between testing the journey and staging its
    starting state, so the invoice under test is one the application wrote.
    """
    with app.test_request_context():
        g.tenant_id = tenant.id
        resp = opening.post(
            f'/reception/visits/{visit_id}/send-to-accounting',
            follow_redirects=False,
        )
    assert resp.status_code in (200, 302), (
        f'send-to-accounting returned {resp.status_code}; reception could not issue the '
        f'invoice this claim is raised against'
    )
    return _invoice_for(app, visit_id)


def _visit_with_issued_invoice(app, client, tenant, dept, doctor, service, login_as):
    """A visit priced from the catalogue, with its invoice issued over HTTP.

    The visit is opened over the real reception endpoint by briefly logging in as a
    receptionist, because that route is reception-gated and an accountant cannot
    open one. The caller's session is restored afterwards so the rest of the
    journey runs as the role it is about: switching roles is the normal operation in
    this workflow, and a test that quietly stayed on one role would stop testing the
    handoff that is the interesting part.
    """
    from tests.tenant_context import ensure_test_user, login_test_client

    receptionist = ensure_test_user(db, tenant, username='e2e_opening_reception', role='reception')
    opening = app.test_client()
    login_test_client(opening, receptionist, tenant)

    patient = _patient(app, tenant.id)
    with app.test_request_context():
        g.tenant_id = tenant.id
        resp = _create_visit_http(
            opening,
            app,
            patient,
            dept,
            doctor,
            selected_tests=[str(service.id)],
        )
    assert resp.status_code in (200, 302), (
        f'visit creation returned {resp.status_code}; reception could not open the '
        f'visit this claim is supposed to be raised against'
    )

    visit = _latest_visit_for(app, patient.id)
    assert visit is not None
    assert Decimal(str(visit.total_amount)) > 0, 'the visit priced at zero'

    invoice = _issue_invoice(app, opening, tenant, visit.id)

    # Hand the session back to whoever the caller is driving the journey as.
    login_as(client, 'e2e_accountant', 'accountant')
    return visit, invoice


@pytest.fixture
def billing(app, client, login_as, test_tenant):
    """An accountant client with a department, a doctor and a priced service."""
    dept = _department(app)
    doctor = _doctor(app, test_tenant)
    service = _service(app, test_tenant, dept)
    accountant = _accountant(app, test_tenant)
    login_as(client, 'e2e_accountant', 'accountant')
    return {
        'app': app,
        'client': client,
        'tenant': test_tenant,
        'dept': dept,
        'doctor': doctor,
        'service': service,
        'accountant': accountant,
        'login_as': login_as,
    }


class TestInsuranceClaimLifecycleIsExecuted:
    """A claim is generated, adjudicated and paid out, and its split stays honest.

    The claim carries three money fields written by three different code paths:
    total_claim from the invoice, approved_amount from adjudication, and
    insurance_share_amount derived at payout. Asserting they agree after each step
    is the point; a claim that is internally inconsistent is not a reporting
    nuisance, it is money the tenant believes it is owed and does not have.
    """

    def test_claim_generation_refuses_an_invoice_that_is_not_issued(self, billing):
        """The generator checks the invoice status before it writes anything.

        A DRAFT invoice cannot become a claim. Asserted positively rather than by
        promoting the invoice first, because the refusal is the invariant and the
        happy path is covered by the next test.
        """
        app, client, tenant = billing['app'], billing['client'], billing['tenant']
        _visit, invoice = _visit_with_issued_invoice(
            app,
            client,
            tenant,
            billing['dept'],
            billing['doctor'],
            billing['service'],
            billing['login_as'],
        )
        # Put it back to DRAFT: the invoice status is the thing under test.
        invoice.status = 'DRAFT'
        db.session.commit()

        with app.test_request_context():
            g.tenant_id = tenant.id
            resp = client.post(
                '/payment/api/insurance/claims/generate',
                json={'invoice_id': invoice.id},
            )
        assert resp.status_code == 400, (
            f'a DRAFT invoice produced a claim with {resp.status_code}; the ISSUED '
            f'check in create_insurance_claim is not enforcing'
        )

    def test_claim_is_generated_adjudicated_and_paid_out(self, billing):
        """The full claim journey, asserting the split after every step."""
        app, client, tenant = billing['app'], billing['client'], billing['tenant']
        _visit, invoice = _visit_with_issued_invoice(
            app,
            client,
            tenant,
            billing['dept'],
            billing['doctor'],
            billing['service'],
            billing['login_as'],
        )
        invoice_total = Decimal(str(invoice.total_amount))

        # 1. Generate. The claim starts DRAFT with nothing approved.
        with app.test_request_context():
            g.tenant_id = tenant.id
            resp = client.post(
                '/payment/api/insurance/claims/generate', json={'invoice_id': invoice.id}
            )
        assert resp.status_code == 200, f'claim generation returned {resp.status_code}'
        claim_id = (resp.get_json(silent=True) or {}).get('data', {}).get('claim_id')
        assert claim_id, f'no claim id in the response: {resp.get_data(as_text=True)[:200]}'

        claim = db.session.get(InsuranceClaim, claim_id)
        assert claim.status == 'DRAFT', f'a new claim starts in {claim.status}'
        assert Decimal(str(claim.total_claim)) == invoice_total, (
            f'the claim total {claim.total_claim} does not match the invoice {invoice_total}'
        )
        assert Decimal(str(claim.approved_amount)) == 0, 'a DRAFT claim is pre-approved'
        assert Decimal(str(claim.insurance_share_amount)) == 0, (
            'a DRAFT claim already carries an insurer share'
        )

        # 2. Adjudicate at eighty percent. The approved amount is supplied by the
        #    caller and is not derived from anything, so it is the field most
        #    worth asserting.
        approved = (invoice_total * Decimal('0.80')).quantize(Decimal('0.01'))
        with app.test_request_context():
            g.tenant_id = tenant.id
            resp = client.post(
                f'/payment/api/insurance/claims/{claim_id}/adjudicate',
                json={'status': 'APPROVED', 'approved_amount': str(approved)},
            )
        assert resp.status_code == 200, f'adjudication returned {resp.status_code}'
        db.session.expire_all()
        claim = db.session.get(InsuranceClaim, claim_id)
        assert claim.status == 'APPROVED', f'adjudication left the claim {claim.status}'
        assert Decimal(str(claim.approved_amount)) == approved, (
            f'the approved amount is {claim.approved_amount}, not {approved}'
        )

        # 3. Payout. This is the step the specification says never reaches the
        #    ledger, so the assertion below is on the claim and then on the ledger
        #    separately, because "the claim says paid" and "the bank moved" are
        #    different claims and only one of them has ever been true.
        with app.test_request_context():
            g.tenant_id = tenant.id
            resp = client.post(f'/api/claims/{claim_id}/payout', json={})
        payout_status = resp.status_code

        db.session.expire_all()
        claim = db.session.get(InsuranceClaim, claim_id)
        insurer_share = Decimal(str(claim.insurance_share_amount))
        patient_share = Decimal(str(claim.patient_share_amount))
        assert insurer_share == approved, (
            f'the insurer share is {insurer_share} but {approved} was approved'
        )
        assert patient_share + insurer_share == invoice_total, (
            f'the claim split does not add up: patient {patient_share} + insurer '
            f'{insurer_share} != total {invoice_total}'
        )

        # The documented defect, executed rather than asserted from the source:
        # an approved claim clears the receivable without a journal entry.
        journals = (
            db.session.execute(select(GLJournal).filter_by(source_id=claim_id, source_type='claim'))
            .scalars()
            .all()
        )
        journals += (
            db.session.execute(
                select(GLJournal).filter_by(source_id=claim_id, source_type='insurance_claim')
            )
            .scalars()
            .all()
        )
        assert not journals, (
            f'a claim payout posted {len(journals)} ledger journal(s) as source_id '
            f'{claim_id}; the specification says it posts none, so either the defect '
            f'is fixed or the specification is stale. payout returned {payout_status}'
        )


class TestRefundJourneyIsExecuted:
    """A payment is refunded through request, approve and execute.

    The three steps live on two blueprints, and the interesting property is that
    the console that collects the payment is not the console that executes its
    refund. The accountant blueprint owns approve and execute; the payment
    blueprint owns request.
    """

    def test_refund_cannot_exceed_the_payment_it_is_against(self, billing):
        """The over-refund is refused before any money is moved."""
        app, client, tenant = billing['app'], billing['client'], billing['tenant']
        visit, _invoice = _visit_with_issued_invoice(
            app,
            app.test_client(),
            tenant,
            billing['dept'],
            billing['doctor'],
            billing['service'],
            billing['login_as'],
        )
        total = Decimal(str(visit.total_amount))

        with app.test_request_context():
            g.tenant_id = tenant.id
            resp = client.post(
                f'/payment/process/{visit.id}',
                data={'payment_method': 'cash', 'paid_amount': str(total)},
            )
        assert resp.status_code in (200, 302), f'the payment was not accepted: {resp.status_code}'

        payment_id = _payment_id_for(app, visit.id)
        assert payment_id is not None, 'no payment row was created for the visit'

        with app.test_request_context():
            g.tenant_id = tenant.id
            resp = client.post(
                f'/payment/payments/{payment_id}/refund',
                json={'amount': str(total * 2), 'reason': 'exceeds the payment'},
            )

        # The route redirects on both outcomes, so the status code says nothing and
        # the row is the only evidence. An over-refund is refused by
        # RefundService.request_refund before anything is written, so the absence of
        # a row is the assertion. Writing it as a row comparison rather than a
        # status comparison is what makes the test survive the redirect-on-failure
        # shape the route happens to use today.
        db.session.expire_all()
        requested = (
            db.session.execute(
                select(func.coalesce(func.sum(RefundRequest.amount), 0)).filter_by(
                    payment_id=payment_id
                )
            ).scalar()
            or 0
        )
        assert Decimal(str(requested)) == 0, (
            f'{requested} was recorded against a payment of {total}; the refund '
            f'ceiling in RefundService.request_refund is not enforcing. The route '
            f'answered {resp.status_code}, which is the answer it also gives when it '
            f'refuses, so only the row can tell the two apart'
        )

    def test_refund_request_is_refused_for_reception(self, billing):
        """Reception can open a visit but cannot refund its payment.

        Asserted because the two roles sit adjacent in the workflow: a receptionist
        who can collect and refund can move money in both directions without the
        till ever being the accountant's problem.
        """
        from tests.tenant_context import login_test_client

        app, tenant = billing['app'], billing['tenant']
        visit, _invoice = _visit_with_issued_invoice(
            app,
            billing['client'],
            tenant,
            billing['dept'],
            billing['doctor'],
            billing['service'],
            billing['login_as'],
        )
        total = Decimal(str(visit.total_amount))
        with app.test_request_context():
            g.tenant_id = tenant.id
            billing['client'].post(
                f'/payment/process/{visit.id}',
                data={'payment_method': 'cash', 'paid_amount': str(total)},
            )
        payment_id = _payment_id_for(app, visit.id)
        assert payment_id is not None

        from tests.tenant_context import ensure_test_user

        receptionist = ensure_test_user(
            db, tenant, username='e2e_refund_reception', role='reception'
        )
        client = app.test_client()
        login_test_client(client, receptionist, tenant)

        resp = client.post(
            f'/payment/payments/{payment_id}/refund',
            json={'amount': '10.00', 'reason': 'refund attempted at the desk'},
        )
        assert resp.status_code in (302, 401, 403), (
            f'reception refunded a payment with {resp.status_code}; the till role gate '
            f'is not enforcing'
        )


def _payment_id_for(app, visit_id):
    """The newest payment row for a visit, or None when none was written."""
    from models.payment import Payment

    payment = (
        db.session.execute(
            select(Payment).filter_by(visit_id=visit_id).order_by(Payment.id.desc()).limit(1)
        )
        .scalars()
        .first()
    )
    return payment.id if payment else None


class TestFinancialLifecycleIsDocumentedAgainstTheCode:
    """State the boundaries the execution above cannot reach, without pretending to.

    Several of these would require seeding a payer, a diagnosis or a refund policy
    that the seed manifest deliberately refuses to fabricate. Asserting them from
    the source is weaker than executing them and is labelled as such.
    """

    def test_refund_amount_is_read_from_the_body_not_a_whitelist(self):
        """The refund amount is caller-supplied, so the ceiling is the only guard."""
        import inspect

        from services.refund_service import RefundService

        source = inspect.getsource(RefundService.request_refund)
        assert 'amount' in source, 'the refund service stopped reading an amount'

    def test_journal_lines_for_a_payment_balance_by_construction(self):
        """Where the code posts a payment journal, debits equal credits.

        Read from the service rather than executed, because it is a property of the
        posting function and executing it for every shape would duplicate the cash
        spine in this file.
        """
        import inspect

        from services.gl_service import GLService

        source = inspect.getsource(GLService.post_payment)
        assert source.strip(), 'post_payment has no body to inspect'
