"""Modular seeding package.

Provides idempotent seeders used to bootstrap the platform:

* ``production_baseline`` — seeds the 14 application modules into the
  ``module_definitions`` registry mirror and creates the master
  ``platform_owner`` account (username ``azad``).
* ``local_dev_story`` — ``--dev`` convenience seed that builds a mock
  tenant ("Azad Dev Hospital"), activates all modules, creates standard
  clinic staff, and links a minimal clinical flow (patient → visit →
  pending lab order → unfilled prescription → unpaid bill).

Because the platform enforces Row-Level Security (tenant scoping) at the ORM
level, every seeder runs inside ``tenant_bypass()`` so global/platform rows
(the master account with ``tenant_id=NULL``, cross-tenant lookups) are not
wrongly scoped or rejected by the fail-closed auto-assign guard.
"""
from contextlib import contextmanager
from flask import g


@contextmanager
def tenant_bypass():
    """Disable tenant RLS filtering/auto-assign for seeding.

    The platform's RLS query filter keys off ``g.tenant_id`` (it is appended
    as ``WHERE tenant_id = :tid`` whenever a tenant context is set), NOT off
    the bypass flag alone. To make global/platform lookups and cross-tenant
    inserts behave, we null ``g.tenant_id`` for the duration.

    IMPORTANT: We do NOT restore the prior tenant context on exit. Seeders
    create global data (``tenant_id=NULL``); callers that need a tenant
    context after seeding must explicitly re-establish it. This avoids the
    common leak where a test fixture's default tenant context gets restored
    and immediately hides the global rows the seeder just created.
    """
    prev_bypass = g.get('_tenant_filter_bypass', False)
    # Clear all tenant-related g keys; do NOT save/restore them.
    g._tenant_filter_bypass = True
    g.tenant_id = None
    g.pop('current_tenant', None)
    g.pop('tenant_slug', None)
    # ``tenant_filter._current_tenant_id`` also reads ``session.info['_tenant_id']``
    # (set by ``bind_g_tenant``). If a prior seeder bound a real tenant,
    # that stale value would still scope global/platform lookups (e.g. the
    # master account with ``tenant_id=NULL``), so clear it here too.
    from app.extensions import db
    db.session.info.pop('_tenant_id', None)
    try:
        yield
    finally:
        if prev_bypass:
            g._tenant_filter_bypass = True
        else:
            g.pop('_tenant_filter_bypass', None)
        # Leave tenant context cleared (None). Callers that need a tenant
        # must explicitly rebind it.
        g.tenant_id = None
        g.pop('current_tenant', None)
        g.pop('tenant_slug', None)
        # Always reset the RLS session var and the PostgreSQL GUC.
        db.session.info.pop('_tenant_id', None)
        try:
            db.session.execute(db.text("SET LOCAL app.tenant_id = ''"))
        except Exception as e:
            # Non-PostgreSQL dialects or missing GUC — ignore gracefully.
            pass
