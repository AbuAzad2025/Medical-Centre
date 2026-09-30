"""S3-017: let every tenant read the platform RBAC catalogue (SELECT only).

Defect: the six RBAC definition tables were declared global at the application
layer but scoped per-tenant at the database layer, and the two layers cancel
each other out.

Application layer, three places that all say "cross-tenant by design":

  * ``app/shared/tenant_filter.py`` -> ``_GLOBAL_TENANT_TABLES`` (the six
    tables are exempt from the ORM tenant filter, so no ``tenant_id``
    predicate is ever emitted for them);
  * ``scripts/ci/audit_rls_coverage.py`` -> ``PLATFORM_TENANT_TABLES`` (RLS is
    *not* required on them, so they are skipped by the coverage audit);
  * ``routes/monitoring_routes.py`` -> its own copy of the same set.

Database layer: ``s2_008_comprehensive_rls_force`` created
``tenant_isolation_<table>`` on all six with

    USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::integer)

The catalogue is written once, under the platform tenant
(``models.permissions._seed_scope`` / ``seeds.production_baseline``), so on a
connection bound to any *other* tenant the policy filtered every row out. The
ORM query that resolves a permission therefore returned nothing and
``PermissionService._resolve_permission`` (``app/core/permission/service.py``)
silently fell through to the hard-coded ``ROLE_PERMISSIONS`` fallback dict --
the database catalogue was never consulted at all.

Observed impact: ``POST /reception/queue/save-settings/<id>``, gated by
``@AccessControlService.require_permission('queue_settings_manage')``, answered
403 for a ``manager`` even though the seeder had granted that exact permission
to that exact role. The grant existed; the policy hid it. Every other gated
route in the suite passed only because its permission happens to appear in the
fallback dict.

This is not a test-harness artefact. In a single-tenant install the platform
tenant *is* the only tenant, so ``app.tenant_id`` equals the catalogue owner and
the path works. Under SaaS (any second tenant) the DB-driven branch of
``_resolve_permission`` is dead for every role except ``super_admin``, which
short-circuits on a wildcard before touching the database. The comment in
``app/shared/tenant_filter.py`` already predicted this exact failure mode
("Scoping them per tenant silently empties every tenant's permission set, which
turns has_permission()/can() into a permanent False and locks staff out of
gated screens"); the policy is what reintroduced it.

The schema settles the design question, so this migration does not treat it as
one. ``roles_name_key`` and ``permissions_name_key`` are UNIQUE on ``name``
alone -- no ``tenant_id`` in the index -- and ``unique_role_permission`` is
UNIQUE on ``(role_id, permission_id)``. A per-tenant catalogue is therefore not
merely undesirable, it is unrepresentable: two tenants cannot both own a row
named ``manager``. The tables are global by constraint; the policy now says so.

Fix: split the single ``FOR ALL`` policy per command.

  * SELECT  -- own tenant *or* the catalogue owner (widened).
  * INSERT / UPDATE / DELETE -- unchanged, still ``tenant_id = GUC`` with
    ``WITH CHECK``. This is the half that must not move: a tenant can resolve
    the platform catalogue but cannot edit it, cannot delete it, and cannot
    mint a grant under another tenant's id.

Identifying the catalogue owner without a GUC: ``seeds.production_baseline``
defines the platform tenant as the bound tenant, else the lowest-id tenant,
else a freshly created ``platform`` slug. So the owner is the lowest-id tenant
on a pre-existing install and the ``platform`` slug on a fresh one, and
matching both covers every database. The predicate is a correlated-free
subquery over ``tenants``, which carries no RLS policy, so it is evaluated
once per statement and stays correct when the platform row is absent (it then
matches nothing beyond the caller's own tenant).

RLS stays ENABLE + FORCE on all six, and the ``tenant_isolation_`` name prefix
is preserved, so ``s3_012_rls_nullif_reassert``'s prefix scan and any external
tooling that greps for it keep working.

Revision: s3_017_rbac_catalogue_readable
Revises: s3_016_backfill_phone_national_id_ngrams
"""

import os
import sys

from alembic import op

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from migration_utils import column_exists, table_exists  # noqa: E402

revision = 's3_017_rbac_catalogue_readable'
down_revision = 's3_016_backfill_phone_national_id_ngrams'
branch_labels = None
depends_on = None

RBAC_CATALOGUE_TABLES = (
    'roles',
    'permissions',
    'role_permissions',
    'user_permissions',
    'module_permissions',
    'department_permissions',
)

# NULLIF wrapper is mandatory: a pooled backend may still carry
# app.tenant_id = '' from a request with no tenant context, and ''::integer
# raises instead of matching nothing (see s1_012, s3_012).
_STRICT = "tenant_id = NULLIF(current_setting('app.tenant_id'::text, true), '')::integer"

_CATALOGUE_OWNER = (
    'tenant_id IN (SELECT t.id FROM tenants t '
    "WHERE t.id = (SELECT min(id) FROM tenants) OR t.slug = 'platform')"
)

_READABLE = f'({_STRICT} OR {_CATALOGUE_OWNER})'


def _policy_names(table: str) -> tuple[str, str, str, str]:
    return (
        f'tenant_isolation_{table}',
        f'tenant_isolation_{table}_insert',
        f'tenant_isolation_{table}_update',
        f'tenant_isolation_{table}_delete',
    )


def _applicable(table: str) -> bool:
    return table_exists(table) and column_exists(table, 'tenant_id')


def upgrade() -> None:
    for table in RBAC_CATALOGUE_TABLES:
        if not _applicable(table):
            continue
        select_pol, insert_pol, update_pol, delete_pol = _policy_names(table)
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
        for name in (select_pol, insert_pol, update_pol, delete_pol):
            op.execute(f'DROP POLICY IF EXISTS {name} ON {table}')
        op.execute(f'CREATE POLICY {select_pol} ON {table} FOR SELECT USING ({_READABLE})')
        op.execute(f'CREATE POLICY {insert_pol} ON {table} FOR INSERT WITH CHECK ({_STRICT})')
        op.execute(
            f'CREATE POLICY {update_pol} ON {table} FOR UPDATE '
            f'USING ({_STRICT}) WITH CHECK ({_STRICT})'
        )
        op.execute(f'CREATE POLICY {delete_pol} ON {table} FOR DELETE USING ({_STRICT})')


def downgrade() -> None:
    for table in RBAC_CATALOGUE_TABLES:
        if not _applicable(table):
            continue
        select_pol, insert_pol, update_pol, delete_pol = _policy_names(table)
        for name in (select_pol, insert_pol, update_pol, delete_pol):
            op.execute(f'DROP POLICY IF EXISTS {name} ON {table}')
        op.execute(
            f'CREATE POLICY {select_pol} ON {table} USING ({_STRICT}) WITH CHECK ({_STRICT})'
        )
