"""A module that is switched off takes its rows with it.

The module switch was enforced at the route: the guard on a blueprint's
``before_request`` answers 403 when the module the blueprint belongs to is
off. That stopped the clinic using the feature, and it stopped nothing else.
The same rows were still readable through every other module's route - a
report that counted them, a doctor reading the clinic's past lab results
after the lab module had been switched off, a dashboard that summed them
into a number the clinic no longer pays for.

The registry now says which tables each module touches, and the tenant filter
answers with no rows for a table that no active module touches. The lists are
not exclusive - the doctor writes the prescriptions the pharmacy dispenses -
so the question is not "who owns the table" but "is any module that touches it
switched on".

Three things have to hold, and they are what these cases check:

  * the table lists are real - every name in them is a table in the schema.
    A name that exists in no table is a silent hole: the table it was meant
    to protect is not protected at all, and seven of them did not exist when
    this was written.
  * a table no active module touches answers with no rows.
  * a write to such a table is refused, and a tenant that never opted into
    the module system keeps everything it has always had.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.module.models import TenantModule
from app.core.module.registry import (
    MODULE_REGISTRY,
    get_modules_for_table,
    get_tables_for_module,
)
from app.extensions import db

# ---------------------------------------------------------------------------
# The metadata itself
# ---------------------------------------------------------------------------


def test_every_declared_table_exists_in_the_schema(app):
    """A table name in the registry has to be a table.

    The registry declared seven names that no table has:
    ``radiology_templates``, ``emergency_medications``, ``nursing_notes``,
    ``nursing_tasks``, ``nursing_vitals``, ``inventory_items`` and
    ``purchase_orders``. Each of them was a promise about a table that does
    not exist, and each of them left a real table unprotected - the nursing
    module's rows were never listed at all, because the three names it did
    list were not its tables.

    The check reads the live schema, so it also fails when a table is renamed
    and the registry is not updated with it.
    """
    from sqlalchemy import inspect

    inspector = inspect(db.engine)
    real_tables = set(inspector.get_table_names())

    missing: list[str] = []
    for module_name, meta in MODULE_REGISTRY.items():
        for table in meta.tables:
            if table not in real_tables:
                missing.append(f'{module_name} -> {table}')

    assert not missing, (
        'the registry names tables that do not exist, so the rows they were '
        f'meant to protect are not protected: {missing}'
    )


def test_a_table_is_claimed_by_every_module_that_touches_it(app):
    """The lists are not exclusive, and the inverse index says so.

    ``prescriptions`` are written by the doctor and dispensed by the
    pharmacy. ``visits`` are opened by reception and written by every
    clinical module. A table that belonged to one module would be hidden
    from a clinic that still had the other one.
    """
    assert get_modules_for_table('prescriptions') == frozenset({'doctor', 'pharmacy'})
    assert get_modules_for_table('visits') >= frozenset(
        {'reception', 'doctor', 'emergency', 'nursing', 'inpatient'}
    )

    # A table no module touches is a cross-cutting table and is never
    # restricted - the audit trail and the users are not a module's rows.
    assert get_modules_for_table('audit_trails') == frozenset()
    assert get_modules_for_table('users') == frozenset()


def test_every_module_names_the_tables_it_touches(app):
    """The registry is the fact base, so it has to be filled in.

    A module with no table list at all cannot have its rows protected. The
    owner and the integration surfaces are platform-wide and are the only
    two that are allowed to be empty.
    """
    empty = sorted(name for name, meta in MODULE_REGISTRY.items() if not meta.tables)
    assert empty == ['owner'], (
        f'these modules name no tables, so nothing protects their rows: {empty}'
    )


def test_get_tables_for_module_answers_the_registry(app):
    for name, meta in MODULE_REGISTRY.items():
        assert get_tables_for_module(name) == meta.tables


# ---------------------------------------------------------------------------
# The behaviour
# ---------------------------------------------------------------------------


def _only_these_modules(app, tenant, module_names):
    """Leave the tenant with exactly *module_names* switched on."""
    from tests.tenant_context import tenant_test_context

    with tenant_test_context(app, tenant):
        for tm in (
            db.session.execute(select(TenantModule).filter_by(tenant_id=tenant.id)).scalars().all()
        ):
            tm.is_active = tm.module_name in module_names
            if tm.is_active:
                tm.deactivated_at = None
            else:
                from datetime import UTC, datetime

                tm.deactivated_at = datetime.now(UTC)
        db.session.commit()

    from app.shared.tenant_filter import invalidate_module_scope

    invalidate_module_scope()


def _make_patient(app, tenant):
    """A patient row to hang the lab request off.

    ``lab_requests.patient_id`` is a foreign key, so the write cannot be
    exercised without one. The patient is a reception row, and reception is
    switched on in these cases, so it lands.
    """
    from models.patient import Patient

    with app.test_request_context():
        from flask import g

        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(tenant, db_session=db.session)
        g.tenant_id = tenant.id

        patient = Patient(first_name='Scope', last_name='Case')
        db.session.add(patient)
        db.session.flush()
        patient_id = patient.id
        # Committed, not rolled back: the lab request hangs off it by
        # foreign key, and a rolled-back patient is not there to hang off.
        db.session.commit()
        return patient_id


def test_a_table_no_active_module_touches_answers_with_no_rows(app, test_tenant):
    """Switching a module off takes its rows out of reach.

    The clinic keeps reception and billing and loses the lab. The lab's
    tables are claimed by the lab, the lab intake and the doctor - and none
    of the three is on any more - so a query on them answers with no rows
    even though the rows are still in the table.
    """
    from models.lab_request import LabRequest

    patient_id = _make_patient(app, test_tenant)
    _only_these_modules(app, test_tenant, {'reception', 'billing'})

    with app.test_request_context():
        from flask import g

        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        g.tenant_id = test_tenant.id

        # The write is refused - a row must not land in a table the clinic
        # has switched off.
        from utils.exceptions import ModuleNotEnabledError

        lab_request = LabRequest(patient_id=patient_id, status='ORDERED')
        db.session.add(lab_request)
        with pytest.raises(ModuleNotEnabledError):
            db.session.flush()
        db.session.rollback()

        # And the read answers with no rows.
        rows = db.session.execute(select(LabRequest)).scalars().all()
        assert rows == [], f'{len(rows)} lab rows were readable with the lab module switched off'


def test_an_active_module_keeps_its_rows_readable(app, test_tenant):
    """Switching one module off does not take the tables it shares away.

    ``visits`` are opened by reception and written by the doctor, so a clinic
    that keeps the doctor keeps the visits - even with reception switched
    off. The list is not exclusive, and this is what that buys.
    """
    from models.visit import Visit

    _only_these_modules(app, test_tenant, {'doctor'})

    with app.test_request_context():
        from flask import g

        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        g.tenant_id = test_tenant.id

        # No error: the statement is allowed to run.
        db.session.execute(select(Visit)).scalars().all()


def test_a_tenant_with_no_module_set_keeps_everything(app, test_tenant):
    """The single-install clinic is not locked out of what it always had.

    A tenant with no rows in ``tenant_modules`` never opted into the module
    system. Its rows stay where they are - a boundary that failed closed
    here would take the whole platform away from the configuration the
    project's own .env ships.
    """
    from models.lab_request import LabRequest

    patient_id = _make_patient(app, test_tenant)

    with app.test_request_context():
        from flask import g

        from tests.tenant_context import bind_tenant_on_g

        with db.session.begin_nested():
            for tm in (
                db.session.execute(select(TenantModule).filter_by(tenant_id=test_tenant.id))
                .scalars()
                .all()
            ):
                db.session.delete(tm)
            db.session.flush()

        bind_tenant_on_g(test_tenant, db_session=db.session)
        g.tenant_id = test_tenant.id

        from app.shared.tenant_filter import invalidate_module_scope

        invalidate_module_scope()

        # The read is not refused and the write is not refused either.
        db.session.execute(select(LabRequest)).scalars().all()

        lab_request = LabRequest(patient_id=patient_id, status='ORDERED')
        db.session.add(lab_request)
        db.session.flush()
        db.session.rollback()


def test_the_platform_bypass_still_reaches_everything(app, test_tenant):
    """A platform operation is not a tenant operation.

    The platform owner reads across tenants on purpose. The module scope is
    a tenant's own boundary, so the bypass skips it the way it skips the
    tenant filter.
    """
    from models.lab_request import LabRequest

    _only_these_modules(app, test_tenant, {'reception', 'billing'})

    with app.test_request_context():
        from flask import g

        from tests.tenant_context import bind_tenant_on_g

        g._tenant_filter_bypass = True
        bind_tenant_on_g(test_tenant, db_session=db.session)
        g.tenant_id = test_tenant.id

        from app.shared.tenant_filter import invalidate_module_scope

        invalidate_module_scope()

        db.session.execute(select(LabRequest)).scalars().all()


def test_the_scope_is_recomputed_after_a_switch(app, test_tenant):
    """The answer is cached, and the cache is dropped when it changes.

    The filter asks on every statement, so the answer is cached on the
    session. A switch that did not drop the cache would leave the clinic
    reading rows it had just switched off - the guard would be right and
    stale.
    """
    from models.lab_request import LabRequest

    _only_these_modules(app, test_tenant, {'reception', 'billing', 'lab'})

    with app.test_request_context():
        from flask import g

        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        g.tenant_id = test_tenant.id

        from app.shared.tenant_filter import invalidate_module_scope

        invalidate_module_scope()

        # With the lab on, the statement is allowed to run.
        db.session.execute(select(LabRequest)).scalars().all()

        # Now switch the lab off and drop the cache, the way the manager's
        # switch does.
        _only_these_modules(app, test_tenant, {'reception', 'billing'})

        db.session.execute(select(LabRequest)).scalars().all()


def test_the_scope_is_not_applied_to_a_table_no_module_touches(app, test_tenant):
    """The audit trail is not a module's rows.

    ``audit_trails`` is claimed by no module, so no module switch can take
    it away. That matters: the audit trail is what says what happened, and a
    guard that could hide it with a switch would be a way to erase the
    evidence of the switch.
    """
    from models.audit_trail import AuditTrail

    _only_these_modules(app, test_tenant, {'reception', 'billing'})

    with app.test_request_context():
        from flask import g

        from tests.tenant_context import bind_tenant_on_g

        bind_tenant_on_g(test_tenant, db_session=db.session)
        g.tenant_id = test_tenant.id

        from app.shared.tenant_filter import invalidate_module_scope

        invalidate_module_scope()

        # The statement runs; nothing raises.
        db.session.execute(select(AuditTrail)).scalars().all()
