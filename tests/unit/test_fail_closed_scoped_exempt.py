"""SaaS fail-closed guards: explicitly tenant-scoped queries need no request context.

In SaaS mode, ``tenant_filter_select`` / ``tenant_filter_query`` raise
``TenantIsolationError`` for tenant-scoped queries executed without a bound
tenant context.  Service-layer code that passes ``tenant_id`` explicitly in
the query (e.g. ``PharmacySaleService.create_sale``) is already scoped to
exactly one tenant, so it must be exempt from the guard; queries with no
tenant scope at all must still fail closed.
"""

import pytest
from sqlalchemy import select

from app.extensions import db
from app.shared.tenant_filter import TenantIsolationError
from models.medication import Prescription


@pytest.mark.no_tenant_context
def test_select_explicit_scope_skips_fail_closed(app, test_tenant, test_medications):
    from tests.tenant_context import clear_tenant_g

    clear_tenant_g()
    stmt = select(Prescription).filter(
        Prescription.id == 1, Prescription.tenant_id == test_tenant.id
    )
    db.session.execute(stmt).scalars().first()


@pytest.mark.no_tenant_context
def test_select_no_scope_still_fails_closed(app, test_tenant, test_medications):
    from tests.tenant_context import clear_tenant_g

    clear_tenant_g()
    stmt = select(Prescription).filter(Prescription.id == 1)
    with pytest.raises(TenantIsolationError):
        db.session.execute(stmt).scalars().first()


@pytest.mark.no_tenant_context
def test_query_explicit_scope_skips_fail_closed(app, test_tenant, test_medications):
    from tests.tenant_context import clear_tenant_g

    clear_tenant_g()
    q = db.session.query(Prescription).filter(
        Prescription.id == 1, Prescription.tenant_id == test_tenant.id
    )
    q.first()
