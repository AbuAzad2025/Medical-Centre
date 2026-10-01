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

from contextlib import contextmanager, suppress

from flask import g


@contextmanager
def tenant_bypass(tenant=None):
    """Disable tenant RLS filtering/auto-assign for seeding.

    Since migration ``s2_001`` made ``tenant_id`` NOT NULL on all tenant-scoped
    tables, seeders can no longer create rows with ``tenant_id=NULL``.  This
    context manager only sets the query-side bypass flag so that cross-tenant
    lookups work *without* filtering.  It does NOT nullify ``g.tenant_id`` or
    clear ``session.info['_tenant_id']``, so ``auto_assign_tenant`` can
    assign the current tenant ID to newly created rows.

    Pass *tenant* to also bind it — the ``g`` fields and the connection's
    ``app.tenant_id``. The bypass alone is not enough to *write*: it suppresses
    the ORM filter, which never reaches the database, so an INSERT naming a
    tenant other than the bound one is rejected by the table's WITH CHECK clause
    with "new row violates row-level security policy". That is what
    ``seeds/local_dev_story.py`` hit on its staff inserts.
    """
    from app.extensions import db

    prev_bypass = g.get('_tenant_filter_bypass', False)
    g._tenant_filter_bypass = True
    prev = None
    if tenant is not None:
        from app.core.tenant.middleware import bind_g_tenant

        prev = (
            g.get('tenant_id'),
            g.get('current_tenant'),
            g.get('tenant_slug'),
            db.session.info.get('_tenant_id'),
        )
        bind_g_tenant(tenant)
    try:
        yield
    finally:
        if prev is not None:
            g.tenant_id, g.current_tenant, g.tenant_slug = prev[0], prev[1], prev[2]
            if prev[3] is None:
                with suppress(Exception):
                    db.session.info.pop('_tenant_id', None)
            else:
                db.session.info['_tenant_id'] = prev[3]
        if prev_bypass:
            g._tenant_filter_bypass = True
        else:
            g.pop('_tenant_filter_bypass', None)
