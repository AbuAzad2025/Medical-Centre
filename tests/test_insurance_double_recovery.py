"""An invoice the patient already paid must not also be claimed from the insurer.

The only gate on raising a claim was the invoice's status, and the payment path
sets paid_amount without moving the status off ISSUED. So a fully paid invoice
still looked claimable, and the centre billed the insurer for the whole invoice
on top of the amount already collected from the patient.
"""

from __future__ import annotations

from decimal import Decimal

from app.extensions import db
from models.invoice import Invoice


def _visit(app, test_tenant, suffix):
    """A patient and a visit, so the invoice has something to belong to."""
    from models.patient import Patient
    from models.visit import Visit

    patient = Patient(
        tenant_id=test_tenant.id,
        first_name=f'Claim{suffix}',
        last_name='Patient',
        national_id=f'E2E-CLAIM-{suffix}',
    )
    db.session.add(patient)
    db.session.flush()
    visit = Visit(
        tenant_id=test_tenant.id,
        patient_id=patient.id,
        status='IN_PROGRESS',
    )
    db.session.add(visit)
    db.session.commit()
    return visit


def test_a_claim_is_refused_on_an_invoice_that_is_already_paid(app, test_tenant):
    """A paid invoice cannot be claimed from the insurer as well."""
    from services.financial_service import FinancialService

    visit = _visit(app, test_tenant, '1')

    invoice = Invoice(
        tenant_id=test_tenant.id,
        visit_id=visit.id,
        total_amount=200.0,
        paid_amount=200.0,
        status='ISSUED',
    )
    db.session.add(invoice)
    db.session.commit()

    result = FinancialService.create_insurance_claim(
        invoice_id=invoice.id,
        tenant_id=test_tenant.id,
        user_id=1,
    )

    assert result['ok'] is False, (
        'a claim was raised on an invoice the patient had already paid in full; '
        'the centre recovers the amount twice'
    )
    assert 'paid' in (result.get('error') or '').lower()


def test_a_claim_is_still_allowed_on_an_unpaid_invoice(app, test_tenant):
    """The guard must not refuse the claim that is legitimate."""
    from services.financial_service import FinancialService

    visit = _visit(app, test_tenant, '2')

    invoice = Invoice(
        tenant_id=test_tenant.id,
        visit_id=visit.id,
        total_amount=Decimal('200.00'),
        paid_amount=Decimal('0.00'),
        status='ISSUED',
    )
    db.session.add(invoice)
    db.session.commit()

    result = FinancialService.create_insurance_claim(
        invoice_id=invoice.id,
        tenant_id=test_tenant.id,
        user_id=1,
    )

    assert result['ok'] is True, (
        f'the claim on an unpaid invoice was refused: {result.get("error")!r}'
    )


def test_the_claim_is_refused_by_the_amount_and_not_by_the_status(app, test_tenant):
    """The status alone was never enough.

    An invoice that is still ISSUED but already has money against it was
    claimable, and that is the shape a paid invoice actually has: the payment
    path sets paid_amount and leaves the status alone.
    """
    from services.financial_service import FinancialService

    visit = _visit(app, test_tenant, '3')

    part_paid = Invoice(
        tenant_id=test_tenant.id,
        visit_id=visit.id,
        total_amount=200.0,
        paid_amount=50.0,
        status='ISSUED',
    )
    db.session.add(part_paid)
    db.session.commit()

    result = FinancialService.create_insurance_claim(
        invoice_id=part_paid.id,
        tenant_id=test_tenant.id,
        user_id=1,
    )
    assert result['ok'] is False, (
        'an invoice with money already against it was still claimable; the status '
        'stays ISSUED when a payment lands'
    )
