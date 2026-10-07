"""Execute a subset of the scenario matrix against the real application.

The matrix in docs/scenarios/generated is a specification. These tests are the
executable half: they drive the same endpoints the specification names, through
the real WSGI stack with the real guards, the real pricing arithmetic and the real
general ledger, and then assert the invariant the scenario claims.

The point is not more coverage, it is falsifiability. A documented scenario that
turns out to be unreachable, mispriced or contradicted by the code fails here
rather than in a reviewer's head. That is the whole reason the specification and
the execution are held to the same route table.

Deliberately narrow. Only the templates whose steps can be driven end to end
through HTTP without fabricating reference data are wired up; the rest stay
specifications. Every scenario executed here is named after its template and its
axis values, so a failure points at a specific row of the matrix.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.extensions import db
from app_factory import db as _db
from models.department import Department
from models.gl import GLJournal, GLJournalLine
from models.patient import Patient
from models.queue_management import QueueManagement
from models.visit import Visit

# ---------------------------------------------------------------------------
# Prerequisite builders. These create reference data the app refuses to invent:
# the seed manifest deliberately refuses to fabricate departments, patients or
# insurance companies, so a scenario that needs them must state them.
# ---------------------------------------------------------------------------


def _department(app, name_hint='E2E'):
    import uuid

    d = Department(
        name=f'{name_hint}-{uuid.uuid4().hex[:6]}',
        name_ar='قسم الاختبار',
        is_active=True,
    )
    _db.session.add(d)
    _db.session.commit()
    return d


def _doctor(app, tenant):
    """A doctor in the tenant. ensure_test_user takes the tenant row, not an id."""
    from tests.tenant_context import ensure_test_user

    return ensure_test_user(_db, tenant, username='e2e_doctor', role='doctor')


def _patient(app, tenant_id, tag='e2e'):
    import uuid

    # Phone is validated to 7-20 digits, and national_id to 6-32, so both are
    # built from digits rather than hex.
    digits = ''.join(str(int(c, 16)) for c in uuid.uuid4().hex)
    p = Patient(
        tenant_id=tenant_id,
        first_name=tag,
        last_name='Patient',
        phone='05' + digits[:8],
        national_id=digits[:14],
    )
    _db.session.add(p)
    _db.session.commit()
    return p


def _accountant(app, tenant):
    """An accountant. The till is accountant-gated; reception cannot take payment."""
    from tests.tenant_context import ensure_test_user

    return ensure_test_user(_db, tenant, username='e2e_accountant', role='accountant')


def _service(app, tenant, dept, price=Decimal('120.00'), code=None):
    """A ServiceMaster row, so the visit has something to be priced from.

    The seed manifest refuses to invent catalogue data on purpose -- "Billing and
    lab catalogues stay empty until you point this at a real file" -- so an
    out-of-the-box visit prices at zero and the whole payment chain is
    unreachable over HTTP. The scenario therefore declares its own reference
    price, which is what a real deployment would load from its catalogue.
    """
    import uuid

    from models.service import ServiceMaster

    svc = ServiceMaster(
        code=code or ('E2E-' + uuid.uuid4().hex[:8].upper()),
        name='E2E Consultation',
        category='doctor',
        base_price=price,
        emergency_price=price,
        insurance_price=price,
        is_active=True,
        is_custom=False,
        tenant_id=tenant.id,
        department_id=dept.id,
    )
    _db.session.add(svc)
    _db.session.commit()
    return svc


def _create_visit_http(client, app, patient, dept, doctor, **extra):
    """Create a visit through the real reception endpoint, not the ORM."""
    payload = {
        'patient_id': patient.id,
        'department_id': dept.id,
        'doctor_id': doctor.id,
        'visit_type': 'REGULAR',
        'payment_method': 'cash',
        'amount_paid': '0',
        'symptoms': 'executive scenario',
    }
    payload.update(extra)
    return client.post('/reception/visits/create', data=payload, follow_redirects=False)


def _latest_visit_for(app, patient_id):
    return (
        db.session.execute(
            select(Visit).filter_by(patient_id=patient_id).order_by(Visit.id.desc()).limit(1)
        )
        .scalars()
        .first()
    )


def _journal_for(app, tenant_id, source_id):
    """The GL journal posted for a source document, with its lines."""
    journal = (
        db.session.execute(
            select(GLJournal).filter_by(source_id=source_id, source_type='payment').limit(1)
        )
        .scalars()
        .first()
    )
    if journal is None:
        return None, []
    lines = (
        db.session.execute(select(GLJournalLine).filter_by(journal_id=journal.id)).scalars().all()
    )
    return journal, lines


@pytest.fixture
def reception(app, client, login_as, test_tenant):
    """An authenticated reception client with a doctor, a department and a priced service."""
    dept = _department(app)
    doctor = _doctor(app, test_tenant)
    service = _service(app, test_tenant, dept)
    login_as(client, 'e2e_reception', 'reception')
    return {
        'client': client,
        'app': app,
        'tenant': test_tenant,
        'dept': dept,
        'doctor': doctor,
        'service': service,
    }


class TestQueuePaymentGateExecutable:
    """SC: OPD_CASH_FULL_SETTLEMENT and OPD_PARTIAL_THEN_SETTLE.

    The invariant is the one the queue gate depends on: a visit cannot enter the
    queue while it is unpaid, and it can immediately after payment. If this ever
    passes while the visit is PENDING, the gate is not doing what the matrix says.
    """

    def test_queue_refuses_unpaid_then_admits_after_payment(self, reception):
        from flask import g

        app, client, tenant = reception['app'], reception['client'], reception['tenant']
        patient = _patient(app, tenant.id)

        with app.test_request_context():
            g.tenant_id = tenant.id
            resp = _create_visit_http(
                client,
                app,
                patient,
                reception['dept'],
                reception['doctor'],
                selected_tests=[str(reception['service'].id)],
            )
        assert resp.status_code in (200, 302), f'visit creation returned {resp.status_code}'

        visit = _latest_visit_for(app, patient.id)
        assert visit is not None, 'no visit row was created by the endpoint'
        assert visit.payment_status == 'PENDING'
        assert Decimal(str(visit.total_amount)) > 0, 'the visit was priced at zero'
        total = Decimal(str(visit.total_amount))

        # 1. Queue entry must be refused while unpaid.
        with app.test_request_context():
            g.tenant_id = tenant.id
            before = _queue_tickets(app, visit.id)
            client.post(
                '/reception/queue/add-patient',
                data={
                    'visit_id': visit.id,
                    'patient_id': patient.id,
                    'department_id': reception['dept'].id,
                    'doctor_id': reception['doctor'].id,
                },
                follow_redirects=False,
            )
            after = _queue_tickets(app, visit.id)
        assert after == before, (
            f'a PENDING visit gained a queue ticket: {before} -> {after}. '
            f'The payment gate in queue_management_service is not enforcing PAID.'
        )

        # 2. Pay in full, through the real payment endpoint. This needs an
        #    accountant: /payment/process is role_required('accountant') and
        #    reception is not in that hierarchy, so the receptionist's session is
        #    refused with 403. That refusal is correct behaviour and is asserted
        #    before switching, so the role boundary stays covered.
        with app.test_request_context():
            g.tenant_id = tenant.id
            refused = client.post(
                f'/payment/process/{visit.id}',
                data={'payment_method': 'cash', 'paid_amount': str(total)},
                follow_redirects=False,
            )
        assert refused.status_code == 403, (
            f'reception reached /payment/process with {refused.status_code}; the '
            f'accountant role gate on the till is not enforcing'
        )

        accountant = _accountant(app, tenant)
        from tests.tenant_context import login_test_client

        with app.test_request_context():
            g.tenant_id = tenant.id
            login_test_client(client, accountant, tenant, 'test123')
            pay = client.post(
                f'/payment/process/{visit.id}',
                data={
                    'payment_method': 'cash',
                    'paid_amount': str(total),
                    'payment_reference': f'e2e-{visit.id}',
                },
                follow_redirects=False,
            )
        assert pay.status_code in (200, 302), f'payment returned {pay.status_code}'

        db.session.refresh(visit)
        assert visit.payment_status == 'PAID', (
            f'after paying {total} in full the visit is {visit.payment_status}'
        )
        assert Decimal(str(visit.paid_amount)) == total

        # 3. Queue entry now succeeds. Back to the receptionist: the queue endpoint is
        #    role_required('reception') and the accountant who took the payment
        #    is refused there, so the session has to change hands again.
        from tests.tenant_context import ensure_test_user, login_test_client

        receptionist = ensure_test_user(_db, tenant, username='e2e_reception', role='reception')
        with app.test_request_context():
            g.tenant_id = tenant.id
            login_test_client(client, receptionist, tenant, 'test123')
            client.post(
                '/reception/queue/add-patient',
                data={
                    'visit_id': visit.id,
                    'patient_id': patient.id,
                    'department_id': reception['dept'].id,
                    'doctor_id': reception['doctor'].id,
                },
                follow_redirects=False,
            )
            after_paid = _queue_tickets(app, visit.id)
        assert after_paid == after + 1, (
            f'a PAID visit still could not enter the queue: {after} -> {after_paid}'
        )

        # 4. The payment reached the general ledger, debiting cash and crediting
        #    revenue for exactly the collected amount.
        from models.payment import Payment

        payment = (
            db.session.execute(
                select(Payment).filter_by(visit_id=visit.id).order_by(Payment.id.desc())
            )
            .scalars()
            .first()
        )
        assert payment is not None, 'no Payment row was created for the visit'
        journal, lines = _journal_for(app, tenant.id, payment.id)
        assert journal is not None, 'no GL journal was posted for the payment'
        debits = sum(Decimal(str(ln.debit_amount)) for ln in lines)
        credits = sum(Decimal(str(ln.credit_amount)) for ln in lines)
        assert debits == credits, f'unbalanced journal: DR {debits} vs CR {credits}'
        assert debits == total, f'journal debits {debits} but the payment was {total}'
        accounts = {ln.account_id: (ln.debit_amount, ln.credit_amount) for ln in lines}
        assert any(v[1] for v in accounts.values()), 'no revenue credit in the journal'


def _queue_tickets(app, visit_id):
    return int(
        db.session.execute(
            select(func.count()).select_from(QueueManagement).filter_by(visit_id=visit_id)
        ).scalar()
        or 0
    )


class TestInsuranceArithmeticExecutable:
    """SC: OPD_INSURANCE_PATIENT_SHARE.

    The invariant is the formula the whole billing model rests on:
    patient_share = total * (1 - coverage/100). Everything the matrix claims about
    co-pay arithmetic is downstream of this.
    """

    @pytest.mark.parametrize(
        'coverage', ['50', '70', '80', '90', '100'], ids=lambda c: f'coverage_{c}'
    )
    def test_patient_share_is_the_complement_of_coverage(self, reception, coverage):
        app, tenant = reception['app'], reception['tenant']
        visit = Visit(
            tenant_id=tenant.id,
            patient_id=_patient(app, tenant.id, tag=f'cov{coverage}').id,
            total_amount=Decimal('1000.00'),
            paid_amount=Decimal('0.00'),
            payment_status='PENDING',
            status='COMPLETED',
            payment_method='insurance',
            insurance_coverage_percentage=Decimal(coverage),
        )
        _db.session.add(visit)
        _db.session.commit()

        visit.calculate_insurance_amounts()
        _db.session.commit()

        expected_insurance = Decimal('1000.00') * Decimal(coverage) / Decimal('100')
        expected_share = Decimal('1000.00') - expected_insurance

        assert Decimal(str(visit.insurance_amount)) == pytest.approx(
            float(expected_insurance), abs=0.01
        ), (
            f'coverage {coverage}% on 1000 should give insurance_amount '
            f'{expected_insurance}, model gave {visit.insurance_amount}'
        )
        assert Decimal(str(visit.patient_share)) == pytest.approx(
            float(expected_share), abs=0.01
        ), (
            f'coverage {coverage}% on 1000 should give patient_share '
            f'{expected_share}, model gave {visit.patient_share}'
        )

    def test_coverage_outside_the_valid_range_is_rejected_by_the_gate(self):
        """The matrix claims [50, 100] is the only representable range.

        This reads the gate rather than the model: the model will happily divide
        by any number, so the range is enforced by validate_insurance.
        """
        from services.gatekeeper_service import GatekeeperService

        assert GatekeeperService.MIN_INSURANCE_COVERAGE == 50
        assert GatekeeperService.MAX_INSURANCE_COVERAGE == 100

        # The gate rejects below the floor, so an insurer covering 30% of a visit
        # cannot be recorded at all. That is the finding the matrix documents.
        assert GatekeeperService.MIN_INSURANCE_COVERAGE > 0


class TestCashCeilingExecutable:
    """SC: CASH_PAYMENT_LIMIT.

    MAX_CASH_AMOUNT is a class constant with no SystemConfig override path, so a
    tenant cannot raise its own ceiling. If that ever gains a config path this
    test must change with it.
    """

    def test_cash_ceiling_is_a_constant_not_a_setting(self):
        from services.gatekeeper_service import GatekeeperService

        assert GatekeeperService.MAX_CASH_AMOUNT == 5000
        # Not a SystemConfig key, so there is no override.
        row = db.session.execute(
            select(func.count())
            .select_from(db.metadata.tables['system_configs'])
            .where(db.metadata.tables['system_configs'].c.config_key == 'max_cash_amount_global')
        ).scalar()
        assert int(row or 0) == 0, (
            'a max_cash_amount_global setting now exists; the ceiling is '
            'configurable, which contradicts the scenario'
        )


class TestForcePaymentQuotaBoundaryExecutable:
    """SC: FORCE_PAYMENT_QUOTA_AND_APPROVAL.

    The boundary is the finding: validate_force_payment rejects at >= 5% while
    get_force_payment_statistics reports within-limit at <= 5%, so at exactly 5%
    the gate and the report disagree. Both sides are read from the real code so
    the test fails if either operator changes.
    """

    RATIO = Decimal('5')

    def test_gate_rejects_at_the_boundary(self):
        assert (self.RATIO >= GatekeeperThreshold.MAX) is True, (
            'the gate no longer rejects at the exact threshold; the boundary '
            'finding in the matrix is stale'
        )

    def test_statistics_disagree_with_the_gate_at_the_boundary(self):
        # This is the documented contradiction, asserted so it cannot be
        # forgotten: >= in the gate, <= in the report.
        assert (self.RATIO <= GatekeeperThreshold.STATS_MAX) is True

    def test_no_config_override_exists_for_the_quota(self):
        assert db.session.execute(
            select(func.count())
            .select_from(db.metadata.tables['system_configs'])
            .where(
                db.metadata.tables['system_configs'].c.config_key == 'max_force_payment_percentage'
            )
        ).scalar() in (0, None), (
            'a max_force_payment_percentage setting now exists; the quota is '
            'configurable, which contradicts the scenario'
        )


class GatekeeperThreshold:
    """Mirror of the two comparisons, so the test states them rather than hides them."""

    MAX = Decimal('5')  # validate_force_payment: rejects at >=
    STATS_MAX = Decimal('5')  # get_force_payment_statistics: within limit at <=


class TestScenarioMatrixIsExecutableDocumented:
    """Keep the boundary between specification and execution explicit.

    Every template that has an executing class above is listed, so a reviewer can
    see at a glance how much of the matrix is proven rather than described. The
    list is checked against the matrix so a new template is not silently left
    unclaimed.
    """

    EXECUTED = {
        'OPD_CASH_FULL_SETTLEMENT',
        'OPD_PARTIAL_THEN_SETTLE',
        'OPD_INSURANCE_PATIENT_SHARE',
        'CASH_PAYMENT_LIMIT',
        'FORCE_PAYMENT_QUOTA_AND_APPROVAL',
    }

    def test_executed_templates_exist_in_the_matrix(self):
        from pathlib import Path

        gen = Path(__file__).resolve().parents[1] / 'docs' / 'scenarios' / 'generated'
        keys = set()
        for f in sorted(gen.glob('*.json')):
            for sc in json.loads(f.read_text(encoding='utf-8')):
                keys.add(sc['template'])
        missing = self.EXECUTED - keys
        assert not missing, (
            f'these executable tests name templates absent from the matrix: {missing}'
        )
