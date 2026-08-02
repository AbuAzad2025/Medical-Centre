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

    Since migration ``s2_001`` made ``tenant_id`` NOT NULL on all tenant-scoped
    tables, seeders can no longer create rows with ``tenant_id=NULL``.  This
    context manager only sets the query-side bypass flag so that cross-tenant
    lookups work *without* filtering.  It does NOT nullify ``g.tenant_id`` or
    clear ``session.info['_tenant_id']``, so ``auto_assign_tenant`` can
    assign the current tenant ID to newly created rows.
    """
    prev_bypass = g.get('_tenant_filter_bypass', False)
    g._tenant_filter_bypass = True
    try:
        yield
    finally:
        if prev_bypass:
            g._tenant_filter_bypass = True
        else:
            g.pop('_tenant_filter_bypass', None)
