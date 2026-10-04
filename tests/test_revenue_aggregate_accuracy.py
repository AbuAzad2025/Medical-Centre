"""Exact-sum verification for the revenue aggregates.

The financial report services aggregate over a filtered subquery::

    select(func.sum(Payment.amount)).select_from(payments_query.subquery())

Naming the base table's column there made SQLAlchemy add ``payments`` to the
FROM clause beside the subquery. The two were combined as a cross join, so every
payment row was repeated once per subquery row and each revenue total came back
multiplied by the number of matching payments. Nothing raised; the reports simply
disagreed with the ledger.

The existing tests for these services asserted only the shape of the result, so
they passed while the numbers were wrong. These assert the arithmetic against
payments whose exact sum is known, and additionally fail if SQLAlchemy emits a
cartesian-product warning, which is the signature of the defect itself.
"""

import warnings
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.exc import SAWarning

from app.extensions import db
from services.advanced_report_service import AdvancedReportService
from services.report_center_service import ReportCenterService

# Deliberately non-uniform: a multiplied total is obvious with these and could
# hide behind equal amounts.
AMOUNTS = [Decimal('10.00'), Decimal('20.00'), Decimal('30.00')]
METHODS = ['CASH', 'CARD', 'INSURANCE']
EXPECTED_TOTAL = Decimal('60.00')


@pytest.fixture
def payments(app, rollback_db):
    """Three known payments in the test tenant, dated today.

    Reads the tenant from ``g`` rather than taking the ``test_tenant`` fixture:
    ``rollback_db`` calls ``db.session.remove()``, which detaches the Tenant
    instance that fixture returns, and touching it afterwards raises
    DetachedInstanceError. The autouse tenant fixture has already bound the id.
    """
    from flask import g

    from models.patient import Patient
    from models.payment import Payment
    from models.visit import Visit

    tenant_id = g.get('tenant_id')
    assert tenant_id is not None, 'autouse fixture should have bound a tenant'

    patient = Patient(first_name='Test', last_name='Patient')
    db.session.add(patient)
    db.session.flush()

    visit = Visit(patient_id=patient.id, tenant_id=tenant_id, status='COMPLETED')
    db.session.add(visit)
    db.session.flush()

    created = []
    for amount, method in zip(AMOUNTS, METHODS, strict=True):
        payment = Payment(
            tenant_id=tenant_id,
            patient_id=patient.id,
            visit_id=visit.id,
            method=method,
            amount=amount,
            status='CONFIRMED',
            payment_date=datetime.now(UTC).replace(tzinfo=None),
        )
        db.session.add(payment)
        created.append(payment)
    db.session.flush()
    return created


def test_financial_analytics_revenue_is_exact_sum(app, payments):
    result = AdvancedReportService.generate_financial_analytics(
        datetime.now(UTC) - timedelta(days=1), datetime.now(UTC) + timedelta(days=1)
    )
    assert result['success'] is True

    payment_analytics = result['analytics']['payments']
    assert payment_analytics['total_count'] == len(AMOUNTS)
    assert Decimal(str(payment_analytics['total_revenue'])) == EXPECTED_TOTAL

    # The per-method breakdown has to add back up to the total. Before the fix
    # each method's amount was itself multiplied by its own row count, so the
    # parts no longer summed to the whole.
    distribution = payment_analytics['method_distribution']
    methods_total = sum(Decimal(str(entry['amount'])) for entry in distribution.values())
    assert methods_total == EXPECTED_TOTAL
    for method, expected in zip(METHODS, AMOUNTS, strict=True):
        assert Decimal(str(distribution[method]['amount'])) == expected, f'{method} mis-summed'
        assert distribution[method]['count'] == 1


def test_financial_analytics_emits_no_cartesian_warning(app, payments):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always', SAWarning)
        AdvancedReportService.generate_financial_analytics(
            datetime.now(UTC) - timedelta(days=1), datetime.now(UTC) + timedelta(days=1)
        )
    cartesian = [str(w.message) for w in caught if 'cartesian' in str(w.message).lower()]
    assert not cartesian, f'unexpected cartesian product: {cartesian}'


def test_compare_periods_revenue_is_exact_sum(app, payments):
    start = datetime.now(UTC) - timedelta(days=1)
    end = datetime.now(UTC) + timedelta(days=1)
    result = ReportCenterService.compare_periods(start, end, start, end)

    # Scope note: compare_periods does not currently apply its date arguments --
    # _range_metrics ignores start_dt/end_dt -- so this asserts the aggregate is
    # exact, not that the windows are respected. Whether to add the missing date
    # filter is a separate decision and is deliberately not taken here.
    assert Decimal(str(result['a']['revenue'])) == EXPECTED_TOTAL
    assert Decimal(str(result['b']['revenue'])) == EXPECTED_TOTAL


def test_compare_periods_emits_no_cartesian_warning(app, payments):
    start = datetime.now(UTC) - timedelta(days=1)
    end = datetime.now(UTC) + timedelta(days=1)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always', SAWarning)
        ReportCenterService.compare_periods(start, end, start, end)
    cartesian = [str(w.message) for w in caught if 'cartesian' in str(w.message).lower()]
    assert not cartesian, f'unexpected cartesian product: {cartesian}'
