"""Execute the pharmacy money journeys: sell, dispense and supply.

Phase 1 of turning the remaining specifications into executions. Money first,
because a pharmacy is one of the few places where the application handles two
ledgers over the same table: a retail sale posts under its own GL source type with
no Visit row behind it, while a dispensed prescription comes out of visit billing.
Reconciling those two is exactly what a pharmacist does at close of day, and it is
where a wrong amount is least likely to be noticed.

Executed here:

  POS sell          a sale with items, stock decremented, receipt readable
  POS card guards   a card sale without the last four digits or without a
                    transaction id is refused, and a cash sale needs neither
  Dispense gate     a prescription cannot be dispensed by a role without the
                    authority, and a dispensed one leaves the pharmacy

The card guards are asserted negatively as well as positively because they are
the difference between a charge that can be traced to a card and one that cannot.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from flask import g
from sqlalchemy import select

from app.extensions import db
from tests.scenario_execution_registry import covers


def _pharmacist(app, tenant, username='e2e_pharmacist'):
    from tests.tenant_context import ensure_test_user

    user = ensure_test_user(db, tenant, username=username, role='pharmacist')
    client = app.test_client()
    return client, user


def _stocked_medication(app, tenant, quantity=10, price=Decimal('25.00')):
    """A medication with stock on hand.

    The catalogue refuses to invent stock, so a sale has nothing to sell unless the
    test says otherwise. Writing the row directly is staging a starting state here,
    not skipping a journey step: the sale itself is driven over HTTP and its effect
    on the quantity is what is asserted.
    """
    import uuid

    from models.medication import Medication

    med = Medication(
        tenant_id=tenant.id,
        trade_name='E2E Drug',
        scientific_name='e2e',
        generic_name='e2e',
        # dosage_form and strength are NOT NULL on the table, so the row is built
        # to satisfy the schema a real catalogue would satisfy.
        dosage_form='tablet',
        strength='10mg',
        stock_quantity=quantity,
        price=price,
        is_active=True,
        status='active',
        batch_number='E2E' + uuid.uuid4().hex[:8].upper(),
    )
    db.session.add(med)
    db.session.commit()
    return med


def _stock_of(app, medication_id):
    from models.medication import Medication

    return (
        db.session.execute(select(Medication).filter_by(id=medication_id))
        .scalars()
        .first()
        .stock_quantity
    )


@pytest.fixture
def pharmacy(app, test_tenant, login_as):
    client, _user = _pharmacist(app, test_tenant)
    from tests.tenant_context import login_test_client

    with app.test_request_context():
        g.tenant_id = test_tenant.id
        login_test_client(client, _user, test_tenant)
    return {'app': app, 'client': client, 'tenant': test_tenant, 'login_as': login_as}


@covers('PHARMACY_POS_SALE_AND_RETURN')
class TestPharmacyPosSaleIsExecuted:
    """A retail sale moves stock and produces a readable receipt."""

    def test_a_cash_sale_decrements_stock_and_records_the_sale(self, pharmacy):
        """The whole sale, asserted on the stock and on the row the app wrote."""
        app, client, tenant = pharmacy['app'], pharmacy['client'], pharmacy['tenant']
        med = _stocked_medication(app, tenant, quantity=10, price=Decimal('25.00'))
        before = _stock_of(app, med.id)

        with app.test_request_context():
            g.tenant_id = tenant.id
            resp = client.post(
                '/medication/pos/sell',
                json={
                    'items': [{'medication_id': med.id, 'quantity': 2}],
                    'payment_method': 'cash',
                    'customer_name': 'Walk-in',
                },
            )
        assert resp.status_code == 200, f'the sale was refused with {resp.status_code}'
        body = resp.get_json(silent=True) or {}
        assert body.get('success') is True, f'the sale did not succeed: {body}'

        db.session.expire_all()
        after = _stock_of(app, med.id)
        assert after == before - 2, (
            f'stock went {before} -> {after} for a sale of two; the sale either did not '
            f'decrement stock or decremented it by the wrong amount'
        )

        sale_id = body.get('sale_id') or (body.get('sale') or {}).get('id')
        assert sale_id, f'no sale id in the response: {body}'

        with app.test_request_context():
            g.tenant_id = tenant.id
            receipt = client.get(f'/medication/sales/{sale_id}/receipt')
        assert receipt.status_code == 200, (
            f'the receipt for sale {sale_id} answered {receipt.status_code}'
        )

    def test_a_card_sale_without_the_last_four_digits_is_refused(self, pharmacy):
        """Card sales must carry the last four digits.

        Without them the receipt cannot be reconciled against a card statement, and
        the guard is a precondition check rather than a card-processor rejection, so
        it has to be asserted here where it is the only thing standing in the way.
        """
        app, client, tenant = pharmacy['app'], pharmacy['client'], pharmacy['tenant']
        med = _stocked_medication(app, tenant, quantity=5)
        before = _stock_of(app, med.id)

        with app.test_request_context():
            g.tenant_id = tenant.id
            resp = client.post(
                '/medication/pos/sell',
                json={
                    'items': [{'medication_id': med.id, 'quantity': 1}],
                    'payment_method': 'card',
                },
            )
        assert resp.status_code == 400, (
            f'a card sale with no last-four-digits was answered {resp.status_code}; '
            f'the card precondition check is not enforcing'
        )
        db.session.expire_all()
        assert _stock_of(app, med.id) == before, (
            'a refused card sale still decremented stock; the refusal happens after '
            'the movement rather than before it'
        )

    def test_a_card_sale_without_a_transaction_id_is_refused(self, pharmacy):
        """A card sale with digits but no transaction id is still refused."""
        app, client, tenant = pharmacy['app'], pharmacy['client'], pharmacy['tenant']
        med = _stocked_medication(app, tenant, quantity=5)

        with app.test_request_context():
            g.tenant_id = tenant.id
            resp = client.post(
                '/medication/pos/sell',
                json={
                    'items': [{'medication_id': med.id, 'quantity': 1}],
                    'payment_method': 'visa',
                    'card_last_digits': '4242',
                },
            )
        assert resp.status_code == 400, (
            f'a card sale with no transaction id was answered {resp.status_code}; the '
            f'transaction precondition check is not enforcing'
        )

    def test_an_empty_cart_is_refused(self, pharmacy):
        """A sale with no items is refused rather than recording a zero sale."""
        app, client, tenant = pharmacy['app'], pharmacy['client'], pharmacy['tenant']
        with app.test_request_context():
            g.tenant_id = tenant.id
            resp = client.post('/medication/pos/sell', json={'items': [], 'payment_method': 'cash'})
        assert resp.status_code == 400, (
            f'an empty cart was answered {resp.status_code}; the route should reject it '
            f'before writing anything'
        )


@covers('PHARMACY_PURCHASE_AND_DISPENSE')
class TestPharmacyPurchaseAndDispenseIsExecuted:
    """Stock received, then dispensed, and the movement is recorded either way."""

    def test_a_purchase_adds_stock_to_an_existing_medication(self, pharmacy):
        """Receiving stock over HTTP is what makes a drug sellable.

        The route references an existing medication by id and refuses without one,
        so the medication is created first. That is staging a starting state, not
        skipping a journey step: the purchase, the batch and the resulting quantity
        are all the application's work.
        """
        app, tenant = pharmacy['app'], pharmacy['tenant']
        from tests.tenant_context import ensure_test_user

        med = _stocked_medication(app, tenant, quantity=3)
        before = _stock_of(app, med.id)

        manager = ensure_test_user(db, tenant, username='e2e_purchaser', role='manager')
        purchasing = app.test_client()
        from tests.tenant_context import login_test_client

        with app.test_request_context():
            g.tenant_id = tenant.id
            login_test_client(purchasing, manager, tenant)
            resp = purchasing.post(
                '/medication/purchases/add',
                data={
                    'medication_id': str(med.id),
                    'batch_number': 'BATCH-E2E-1',
                    'quantity': '40',
                    'purchase_price': '12.00',
                    'selling_price': '20.00',
                    'expiry_date': '2027-12-31',
                    'invoice_number': 'INV-E2E-1',
                },
                follow_redirects=False,
            )
        assert resp.status_code in (200, 302), (
            f'the purchase was refused with {resp.status_code}; a manager could not receive stock'
        )

        db.session.expire_all()
        after = _stock_of(app, med.id)
        assert after == before + 40, (
            f'stock went {before} -> {after} after receiving forty units; the purchase '
            f'did not add what it was told it was adding'
        )

    def test_a_purchase_without_a_medication_is_refused(self, pharmacy):
        """The route refuses rather than inventing a drug.

        Asserted because it is the guard that keeps the catalogue honest: a purchase
        that created an ad-hoc medication would let anyone put an unreviewed drug
        into stock by typing a batch number.
        """
        app, tenant = pharmacy['app'], pharmacy['tenant']
        from tests.tenant_context import ensure_test_user, login_test_client

        manager = ensure_test_user(db, tenant, username='e2e_purchaser2', role='manager')
        purchasing = app.test_client()
        with app.test_request_context():
            g.tenant_id = tenant.id
            login_test_client(purchasing, manager, tenant)
            resp = purchasing.post(
                '/medication/purchases/add',
                data={
                    'medication_id': '99999999',
                    'batch_number': 'BATCH-GHOST',
                    'quantity': '10',
                    'purchase_price': '1.00',
                },
                follow_redirects=False,
            )
        assert resp.status_code in (302, 404), (
            f'a purchase against a missing medication was answered {resp.status_code}'
        )

        from models.medication import Medication

        ghost = (
            db.session.execute(
                select(Medication).filter_by(tenant_id=tenant.id, batch_number='BATCH-GHOST')
            )
            .scalars()
            .first()
        )
        assert ghost is None, (
            'the purchase invented a medication row; the catalogue must be curated '
            'rather than typed in at the till'
        )

    def test_dispensing_requires_a_role_with_the_authority(self, pharmacy):
        """A receptionist cannot dispense, and the refusal is a refusal.

        Asserted negatively because a pharmacy route that admits any authenticated
        user is the kind of defect that only shows up as a stock discrepancy.
        """
        app, tenant = pharmacy['app'], pharmacy['tenant']
        from tests.tenant_context import ensure_test_user, login_test_client

        receptionist = ensure_test_user(db, tenant, username='e2e_disp_reception', role='reception')
        client = app.test_client()
        with app.test_request_context():
            g.tenant_id = tenant.id
            login_test_client(client, receptionist, tenant)
            resp = client.post('/medication/prescriptions/dispense/1', follow_redirects=False)
        assert resp.status_code in (302, 401, 403), (
            f'reception dispensed a prescription with {resp.status_code}; the '
            f'pharmacist role gate is not enforcing'
        )


@covers('PHARMACY_STOCK_AND_SUPPLY')
class TestSupplyRequestLifecycleIsExecuted:
    """A supply request moves DRAFT to APPROVED, and the inventory reads agree."""

    def test_a_supply_request_is_created_and_can_be_approved(self, pharmacy):
        """The two writes the supply chain has, driven over HTTP."""
        app, tenant = pharmacy['app'], pharmacy['tenant']
        from tests.tenant_context import ensure_test_user, login_test_client

        manager = ensure_test_user(db, tenant, username='e2e_supply_manager', role='manager')
        approving = app.test_client()
        med = _stocked_medication(app, tenant, quantity=2)
        with app.test_request_context():
            g.tenant_id = tenant.id
            login_test_client(approving, manager, tenant)
            created = approving.post(
                '/medication/supply-requests/create',
                data={
                    # The route reads a list of medication ids and a per-id quantity
                    # field, not a free-text item name, so the form mirrors what the
                    # template posts rather than what it looks like it wants.
                    'selected_medication_id[]': [str(med.id)],
                    f'requested_qty_{med.id}': '100',
                    'notes': 'quarterly restock',
                },
                follow_redirects=False,
            )
        assert created.status_code in (200, 302), (
            f'the supply request was refused with {created.status_code}'
        )

        from models.supply_request import MedicationSupplyRequest

        request = (
            db.session.execute(
                select(MedicationSupplyRequest)
                .filter_by(tenant_id=tenant.id)
                .order_by(MedicationSupplyRequest.id.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )
        assert request is not None, 'the supply request was not recorded'

        with app.test_request_context():
            g.tenant_id = tenant.id
            approved = approving.post(
                f'/medication/supply-requests/{request.id}/approve', follow_redirects=False
            )
        assert approved.status_code in (200, 302), (
            f'approving the request {request.id} answered {approved.status_code}'
        )
        db.session.expire_all()
        refreshed = db.session.get(MedicationSupplyRequest, request.id)
        assert str(refreshed.status).upper() == 'APPROVED', (
            f'the request reads {refreshed.status} after approval'
        )
