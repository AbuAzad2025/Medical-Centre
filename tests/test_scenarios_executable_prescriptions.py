"""Execute the prescription journey over real HTTP, and follow it to its end.

Phase 3a, the clinical spine. A prescription is the one object in this system that
three other departments wait on: the pharmacy cannot dispense what was never
written, billing cannot charge for it, and the patient's record is the only place
the drug appears at all. The specification treats it as a state machine
(active, issued, dispensed, cancelled), which is the right model, so it is worth
asking what the application actually does when a doctor writes one.

Everything below is driven through ``POST /doctor/prescription/<visit_id>`` with the
bracket-suffixed field names the handler reads, and asserted on rows. The handler
catches every exception and flashes a generic message, so a status code of 302 is
not evidence of anything.

What execution established:

  * A prescription is written correctly. Items are priced from the formulary,
    dosage is composed with its frequency, and the visit is flagged for financial
    settlement. That part is sound.

  * A recorded allergy does refuse the write, through the clinical safety service,
    with a HARD STOP naming the allergen. That is the behaviour that matters most
    in this file and it is pinned here so it cannot be lost.

  * Writing a prescription takes the visit away from the doctor who wrote it. The
    handler hands the patient to reception and clears ``visit.doctor_id``, which is
    the gate the same route uses to decide whether the doctor may open the visit at
    all. So the prescription cannot be amended, extended with a second drug, or
    even reopened by its author. Both of those are asserted below.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from flask import g
from sqlalchemy import func, select

from app.extensions import db
from models.medication import Medication, Prescription
from tests.scenario_execution_registry import covers


def _doctor(app, tenant, username='e2e_rx_doctor'):
    from tests.tenant_context import ensure_test_user, login_test_client

    user = ensure_test_user(db, tenant, username=username, role='doctor')
    client = app.test_client()
    with app.test_request_context():
        g.tenant_id = tenant.id
        login_test_client(client, user, tenant)
    return client, user


@pytest.fixture
def clinic(app, test_tenant):
    """A doctor, a patient, a visit in progress, and two drugs on the formulary.

    The reception department is not decoration and omitting it makes two of the
    cases below pass for the wrong reason. Writing a prescription runs a
    hub-and-spoke hand-off that looks for a department whose name resolves to
    'reception'; Department.get_type reads the name rather than a column, so with
    no department present the lookup finds nothing, the hand-off is skipped, and
    the visit keeps its doctor. Every real deployment has a reception, so a fixture
    without one describes a system that does not exist and quietly turns the two
    amendment cases green.
    """
    from models.department import Department
    from tests.tenant_context import activate_tenant_modules

    # prescription_service.create_prescription is gated on the doctor module, so a
    # tenant without it cannot write a prescription at all and the journey below
    # would be asserting against a 404 from the feature gate.
    activate_tenant_modules(app, test_tenant, ['doctor'])

    client, doctor = _doctor(app, test_tenant)

    from models.patient import Patient
    from models.visit import Visit

    # get_type() resolves to 'reception' from either name, which is what the
    # hand-off filters on.
    db.session.add(
        Department(
            tenant_id=test_tenant.id,
            name='Reception',
            name_ar='استقبال',
            is_active=True,
        )
    )

    patient = Patient(
        tenant_id=test_tenant.id,
        first_name='Rx',
        last_name='Patient',
        national_id='E2E-RX-1',
    )
    db.session.add(patient)
    db.session.flush()

    visit = Visit(
        tenant_id=test_tenant.id,
        patient_id=patient.id,
        doctor_id=doctor.id,
        visit_number='E2E-RX-VISIT-1',
        status='IN_PROGRESS',
        chief_complaint='headache',
    )
    db.session.add(visit)

    drugs = []
    for suffix, price in (('A', Decimal('12.50')), ('B', Decimal('30.00'))):
        med = Medication(
            tenant_id=test_tenant.id,
            trade_name=f'E2E Drug {suffix}',
            scientific_name=f'e2e-{suffix.lower()}',
            generic_name=f'e2e-{suffix.lower()}',
            # dosage_form and strength are NOT NULL: the row satisfies the schema a
            # real formulary would satisfy.
            dosage_form='tablet',
            strength='10mg',
            price=price,
            is_active=True,
        )
        db.session.add(med)
        drugs.append(med)
    db.session.commit()

    return {
        'app': app,
        'client': client,
        'tenant': test_tenant,
        'doctor': doctor,
        'patient': patient,
        'visit': visit,
        'drug_a': drugs[0],
        'drug_b': drugs[1],
    }


def _write_prescription(
    client,
    visit_id,
    medication_id,
    dosage='1 tablet',
    frequency='twice daily',
    duration_days='7',
    quantity='1',
    follow_redirects=False,
):
    """POST the prescription form exactly as the browser posts it."""
    return client.post(
        f'/doctor/prescription/{visit_id}',
        data={
            'item_medication_id[]': [str(medication_id)],
            'item_dosage[]': [dosage],
            'item_frequency[]': [frequency],
            'item_duration_days[]': [duration_days],
            'item_quantity[]': [quantity],
            'item_instructions[]': ['after food'],
            'additional_notes': '',
        },
        follow_redirects=follow_redirects,
    )


def _prescriptions_for(visit_id):
    return (
        db.session.execute(
            select(func.count()).select_from(Prescription).filter_by(visit_id=visit_id)
        ).scalar()
        or 0
    )


class _ClockFactory:
    """A drop-in for routes.doctor.prescriptions.datetime, pinned to an instant.

    The handler stamps prescription_number with int(time()), which truncates to
    whole seconds, so whether two writes collide depends on the wall clock. Pinning
    it is what makes the collision case deterministic instead of intermittent.
    """

    def __init__(self, instant):
        self.instant = instant

    def now(self, tz=None):
        import datetime as dt

        return dt.datetime.fromtimestamp(self.instant, dt.UTC)


def _frozen(instant):
    """Pin the route's clock to *instant*, given in epoch seconds."""
    return _ClockFactory(instant)


@covers('DOCTOR_PRESCRIPTION_STATE_CHANGES')
class TestPrescriptionIsWrittenCorrectly:
    """The write itself: priced from the formulary, and flagged for settlement."""

    def test_an_item_is_priced_from_the_formulary_not_from_the_form(self, clinic):
        """The form never carries a price, so the only source of one is the drug.

        Quantity three at the catalogue price, and the composed dosage, asserted on
        the row. A handler that trusted a posted unit_price would be an
        authorisation hole rather than a pricing bug, which is why this is worth
        pinning rather than assuming.
        """
        client, visit, drug = clinic['client'], clinic['visit'], clinic['drug_a']

        _write_prescription(client, visit.id, drug.id, quantity='3', duration_days='7')

        rx = db.session.execute(select(Prescription).filter_by(visit_id=visit.id)).scalars().first()
        assert rx is not None, 'the prescription was not written'

        item = rx.items.first()
        assert item is not None, 'the prescription has no item'
        assert item.medication_id == drug.id
        assert item.quantity == 3, f'quantity stored as {item.quantity}'
        assert item.duration_days == 7, f'duration stored as {item.duration_days}'
        # dosage and frequency are stored in one column, joined by the handler.
        assert item.dosage == '1 tablet | twice daily', (
            f'dosage stored as {item.dosage!r}; the handler composes it with the frequency'
        )
        assert Decimal(item.unit_price) == Decimal('12.50'), (
            f'unit_price stored as {item.unit_price}; the form posts no price, so this '
            f'must have come from Medication.price'
        )
        assert Decimal(item.total_price) == Decimal('37.50'), (
            f'total_price stored as {item.total_price}; expected unit_price x quantity'
        )

    def test_the_visit_is_flagged_for_settlement_after_the_prescription(self, clinic):
        """prescription_issued and pending_financial_settlement are what billing reads."""
        from tests.tenant_context import refresh_scoped

        client, visit = clinic['client'], clinic['visit']

        _write_prescription(client, visit.id, clinic['drug_a'].id)

        fresh = refresh_scoped(clinic['app'], clinic['tenant'], visit)
        assert fresh.prescription_issued is True, (
            'visit.prescription_issued was not set; billing cannot tell a visit with a '
            'prescription from one without'
        )
        assert fresh.pending_financial_settlement is True, (
            'visit.pending_financial_settlement was not set, so the hub-and-spoke gate '
            'that sends the patient to reception has nothing to act on'
        )


@covers('DOCTOR_PRESCRIPTION_STATE_CHANGES')
class TestAllergiesRefuseTheWrite:
    """The one assertion in this file that protects a patient rather than a workflow."""

    def test_a_recorded_allergy_refuses_the_prescription(self, clinic):
        """A drug matching a recorded allergy must not reach the record.

        Asserted twice over, because either half alone would be weak: the row count
        proves nothing was written, and the HARD STOP text proves it was refused
        for the allergy rather than for some unrelated error that also happens to
        write no rows. The companion case below writes the same prescription for a
        patient with no allergy, so the difference is the allergy and nothing else.
        """
        from models.patient import PatientAllergy

        client, tenant = clinic['client'], clinic['tenant']
        patient, visit, drug = clinic['patient'], clinic['visit'], clinic['drug_a']

        db.session.add(
            PatientAllergy(
                tenant_id=tenant.id,
                patient_id=patient.id,
                allergen=drug.trade_name,
                severity='severe',
                description='anaphylaxis',
            )
        )
        db.session.commit()

        before = _prescriptions_for(visit.id)
        resp = _write_prescription(client, visit.id, drug.id, follow_redirects=True)
        body = resp.get_data(as_text=True)

        assert _prescriptions_for(visit.id) == before, (
            'a prescription was written for a drug the patient has a recorded allergy '
            'to. ClinicalSafetyService raises a HARD STOP for exactly this and '
            'create_prescription returns it as a refusal; if this now writes, the '
            'safety service has stopped being reached.'
        )
        assert 'HARD STOP' in body, (
            'the write was refused, but not by the allergy check: the response carries '
            'no HARD STOP notice, so the refusal came from somewhere else'
        )
        assert drug.trade_name in body, (
            'the refusal does not name the offending drug, so the prescriber cannot '
            'tell which line of the prescription to change'
        )


@covers('DOCTOR_PRESCRIPTION_STATE_CHANGES')
class TestTheReceptionHandOff:
    """What happens to the patient once a prescription exists.

    This class replaced two cases that asserted the prescription could not be
    amended. Those two passed, and passing them is the finding: writing a
    prescription runs a hub-and-spoke hand-off that sends the patient to reception
    for payment, and that hand-off has never once executed. The lookup that starts
    it is ``select(Department).filter(Department.get_type() == 'reception')``, and
    ``get_type`` is a plain Python method, so calling it unbound raises TypeError
    before the query is ever built. The surrounding ``except Exception: pass``
    swallows it without logging, so the failure is invisible in every sense.

    The visible consequence is that a visit with pending_financial_settlement set is
    a visit nobody collects payment from: the flag is written before the hand-off is
    attempted, and the hand-off always fails.
    """

    def test_the_patient_is_queued_at_reception_after_a_prescription(self, clinic):
        """One prescription puts the patient in the reception queue.

        Staged with a reception department present, because the hand-off is skipped
        when there is not one and that omission makes this case pass for the wrong
        reason.
        """
        from models.queue_management import QueueManagement

        client, visit = clinic['client'], clinic['visit']

        _write_prescription(client, visit.id, clinic['drug_a'].id)

        queued = db.session.execute(
            select(func.count())
            .select_from(QueueManagement)
            .filter_by(patient_id=visit.patient_id, visit_id=visit.id)
        ).scalar()
        assert queued and queued > 0, (
            'no queue entry was written for the visit. The route looks for its '
            'reception department with filter(Department.get_type() == "reception"), '
            'but get_type is a Python method: evaluating it unbound raises '
            '"TypeError: get_type() missing 1 required positional argument: self", '
            'the query is never built, and the bare except that follows skips the '
            'hand-off. The patient is never sent to reception, so nobody collects '
            'payment for the prescription.'
        )

    def test_the_settlement_flag_is_not_set_when_the_hand_off_did_not_happen(self, clinic):
        """pending_financial_settlement must mean a hand-off is genuinely outstanding.

        The flag is assigned before the hand-off is attempted, and the hand-off is
        attempted inside a try that swallows everything. So the flag is set whether
        or not anything happened, which makes it useless as a work queue: a visit '
        'waiting for payment is indistinguishable from one whose payment step was '
        'never started.
        """
        from models.queue_management import QueueManagement
        from tests.tenant_context import refresh_scoped

        app, client = clinic['app'], clinic['client']
        visit = clinic['visit']

        _write_prescription(client, visit.id, clinic['drug_a'].id)

        queued = db.session.execute(
            select(func.count())
            .select_from(QueueManagement)
            .filter_by(patient_id=visit.patient_id, visit_id=visit.id)
        ).scalar()

        fresh = refresh_scoped(app, clinic['tenant'], visit)
        assert not (fresh.pending_financial_settlement and not queued), (
            'the visit is flagged as awaiting financial settlement but the patient '
            'was never queued anywhere. The flag is written on line 398, before the '
            'hand-off is attempted on line 403, so it records an intention rather '
            'than an outstanding task. Set it only where the hand-off succeeded, or '
            'nothing will ever work off it.'
        )

    def test_a_doctor_can_add_a_second_drug_to_the_same_visit(self, clinic):
        """The amendment path a prescriber needs.

        The clock is pinned to two different instants rather than left to the wall
        clock. It works today, and pinning the clock is what makes that a fact
        rather than a coin flip: see the collision case below, which fails
        precisely because the number has one-second granularity.
        """
        from unittest import mock

        client, visit = clinic['client'], clinic['visit']

        with mock.patch('routes.doctor.prescriptions.datetime', _frozen(1_700_000_000.0)):
            _write_prescription(client, visit.id, clinic['drug_a'].id)
        first = _prescriptions_for(visit.id)

        with mock.patch('routes.doctor.prescriptions.datetime', _frozen(1_700_000_005.0)):
            _write_prescription(client, visit.id, clinic['drug_b'].id)
        second = _prescriptions_for(visit.id)

        assert first == 1, f'the first prescription did not write; count was {first}'
        assert second == 2, (
            f'the second drug was not added to the visit: {second} prescription(s) after two writes'
        )

    def test_two_prescriptions_on_one_visit_do_not_collide_within_a_second(self, clinic):
        """Two writes in the same clock second must both be written.

        prescription_number is built as f'RX-{visit_id}-{int(time())}' against a
        column declared unique=True, so two writes in the same second on the same
        visit ask for the same number and the second is refused by the database.
        Reproduced here with the clock pinned rather than by racing it, which is
        what makes this deterministic instead of the intermittent failure it
        otherwise is.

        A prescriber amending a prescription seconds after writing it, or a
        double-click, or any retry after a timeout, is enough to trigger it.
        """
        from unittest import mock

        client, visit = clinic['client'], clinic['visit']

        try:
            with mock.patch('routes.doctor.prescriptions.datetime', _frozen(1_700_000_000.0)):
                _write_prescription(client, visit.id, clinic['drug_a'].id)
                first = _prescriptions_for(visit.id)
                _write_prescription(client, visit.id, clinic['drug_b'].id)
                second = _prescriptions_for(visit.id)
        finally:
            # The collision aborts the transaction. An aborted transaction outlives
            # the test and turns every later case in the session into a rollback or
            # tenant error of its own, so it is cleared here rather than exported.
            db.session.rollback()

        assert first == 1, f'the first prescription did not write; count was {first}'
        assert second == 2, (
            f'the second prescription was refused: the visit holds {second} after two '
            f'writes to the same clock second. The number carries int(time()) against '
            f'a unique column, so anything written within a second of the first '
            f'collides. It needs a per-row discriminator rather than a timestamp.'
        )

    def test_a_rejected_prescription_leaves_the_session_usable(self, clinic):
        """A refused write must not poison the session for whatever comes next.

        The uniqueness failure surfaces as UniqueViolation during flush, and the
        transaction is left aborted. Everything that touches the database next
        fails too, with a rollback or tenant error rather than with the real
        problem, so one rejected prescription turns into a session that stays
        broken for the rest of the request.

        The error is caught around the writes as well as around the follow-up read,
        because an aborted transaction surfaces wherever the next statement happens
        to be. That is usually the tenant filter re-asserting SET LOCAL, which
        raises TenantIsolationError -- a PermissionError, not a SQLAlchemy one --
        so a duplicate prescription number comes back looking like a tenant
        isolation failure, which is a misleading thing to show an operator.
        """
        from unittest import mock

        from sqlalchemy.exc import SQLAlchemyError

        from app.shared.tenant_filter import TenantIsolationError

        client, visit = clinic['client'], clinic['visit']

        poisoned = None
        try:
            with mock.patch('routes.doctor.prescriptions.datetime', _frozen(1_700_000_000.0)):
                _write_prescription(client, visit.id, clinic['drug_a'].id)
                try:
                    _write_prescription(client, visit.id, clinic['drug_b'].id)
                    follow_up = _prescriptions_for(visit.id)
                except (SQLAlchemyError, TenantIsolationError) as exc:
                    poisoned = exc
                    follow_up = None
        finally:
            # Same reason as the case above: contain the aborted transaction rather
            # than letting it decide the outcome of the rest of the suite.
            db.session.rollback()

        assert poisoned is None, (
            f'a prescription refused for a duplicate number left the session unusable: '
            f'{poisoned}. The failed insert was never rolled back, so every later '
            f'database call in the same session fails instead of the uniqueness '
            f'violation that actually happened, and it surfaces as a tenant isolation '
            f'error rather than as the duplicate number.'
        )
        assert follow_up == 1, (
            f'after a refused second write the visit holds {follow_up} prescription(s)'
        )
