"""
Tenant Data Isolation Layer
Auto-injects tenant_id = g.tenant_id into every query/insert/update/delete.

Three hooks:
  1. before_compile (Query) — auto-filters SELECT queries
  2. before_flush (Session) — auto-assigns tenant_id on INSERT + bundle limit check
  3. before_update_delete (Session) — prevents cross-tenant UPDATE/DELETE

Fail-closed: in SaaS mode, queries on tenant-scoped models MUST have a
tenant_id in context or an explicit bypass flag.  Without one, an
AuthorizationError is raised to prevent data leaks.
"""
import logging

from flask import current_app, g
from sqlalchemy import event
from sqlalchemy.sql.elements import TextClause
from sqlalchemy.orm import Query, Session as OrmSession
from app.extensions import db

logger = logging.getLogger(__name__)


class TenantIsolationError(PermissionError):
    """Raised when a tenant-scoped query executes without tenant context in SaaS mode."""


# ---------------------------------------------------------------------------
# GLOBAL TABLE DETECTION
#
# Two-layer dynamic detection:
# 1. Models WITHOUT a 'tenant_id' column → inherently global, no filtering.
# 2. Models WITH 'tenant_id' but listed in _GLOBAL_TENANT_TABLES →
#    cross-tenant by design (e.g., auth tables, tenant registry).
#
# Adding a new model to the database is automatically handled — no manual
# edits to this file needed for new tenant-scoped or global tables.
# ---------------------------------------------------------------------------

# Tables that DO have a tenant_id column but are global / cross-tenant
# by design and must NOT be tenant-filtered.
#
# NOTE: Keep ``scripts/ci/audit_rls_coverage.py`` in sync — its
# ``PLATFORM_TENANT_TABLES`` must mirror this set exactly.
_GLOBAL_TENANT_TABLES = frozenset({
    'tenants',
    'roles', 'permissions', 'role_permissions', 'user_permissions',
    'module_permissions', 'department_permissions',
    'system_configs', 'branding_settings',
    'platform_audit_logs',  # has tenant_id column but is cross-tenant audit trail
})


def _skip_table(model_class) -> bool:
    """Determine if a model is global (non-tenant-scoped).

    Uses dynamic detection:
    1. If the model lacks a 'tenant_id' mapped column → inherently global.
       No hardcoded table-name list needed — metadata introspection
       automatically handles all tables without tenant_id.
    2. If the model has 'tenant_id' but is in the ``_GLOBAL_TENANT_TABLES``
       allowlist → cross-tenant by design (tenant registry, auth tables,
       system configs, etc.).
    3. Otherwise → tenant-scoped (subject to tenant filtering).
    """
    mapper = getattr(model_class, '__mapper__', None)
    if mapper is None:
        return False  # Can't determine — treat as tenant-scoped (fail-safe)
    if 'tenant_id' not in mapper.columns:
        return True  # No tenant_id column → inherently global
    name = getattr(model_class, '__tablename__', '')
    return name in _GLOBAL_TENANT_TABLES


# ---------------------------------------------------------------------------
# GLOBAL SESSION.GET() GUARD — catch cross-tenant loads from pk lookups
# ---------------------------------------------------------------------------

@event.listens_for(OrmSession, 'loaded_as_persistent')
def _guard_session_get(target, context):
    """Fail-closed guard for ``db.session.get()`` which bypasses the
    ``before_compile`` tenant filter.

    ``session.get(Model, pk)`` does not go through the Query pipeline,
    so the ``tenant_filter_query`` listener cannot intercept it.  This
    listener fires for *every* object the session loads from the database
    (including eager-loaded relationships, deferred columns, and
    ``session.get()`` lookups) and verifies the object's ``tenant_id``
    matches the current context.

    Explicitly skipped:
    - Objects whose model lacks a ``tenant_id`` column (global tables).
    - Objects whose model is in the ``_skip_table()`` allowlist.
    - Operations under ``_tenant_filter_bypass`` (platform / super-admin).
    """
    if _is_tenant_bypass():
        return

    mapper = getattr(target, '__mapper__', None)
    if mapper is None or 'tenant_id' not in mapper.columns:
        return
    if _skip_table(target.__class__):
        return

    tid = _current_tenant_id()
    if tid is None:
        # In SaaS mode, any load of a tenant-scoped object without a
        # tenant context is suspicious — fail closed.
        if _is_saas_mode():
            raise TenantIsolationError(
                f"Tenant-scoped object {target.__class__.__name__}:{getattr(target, 'id', '?')} "
                f"loaded without tenant context"
            )
        return

    instance_tid = getattr(target, 'tenant_id', None)
    if instance_tid is not None and instance_tid != tid:
        raise PermissionError(
            f"Cross-tenant access blocked via session.get(): "
            f"{target.__class__.__name__}:{getattr(target, 'id', '?')} "
            f"(tenant={instance_tid}) does not belong to current tenant (tenant={tid})"
        )


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _is_saas_mode() -> bool:
    try:
        return current_app.config.get('ENABLE_SAAS_MODE', False)
    except RuntimeError:
        return False


def _current_tenant_id(session=None):
    """Return tenant_id from session.info or Flask g, or None."""
    if session is not None:
        tid = session.info.get('_tenant_id')
        if tid is not None:
            return tid
    try:
        return g.get('tenant_id')
    except RuntimeError:
        return None


def _is_tenant_bypass() -> bool:
    """Check if the current context explicitly bypasses tenant filtering."""
    try:
        return g.get('_tenant_filter_bypass', False)
    except RuntimeError:
        return False


# ---------------------------------------------------------------------------
# 1a. SOFT-DELETE FILTER — every SELECT gets WHERE deleted_at IS NULL
# ---------------------------------------------------------------------------

# Common soft-delete column names (configurable if needed)
_SOFT_DELETE_COLUMNS = frozenset({'deleted_at', 'is_deleted', 'deleted'})

def _model_has_soft_delete(model_class) -> bool:
    """Check if model has a soft-delete column."""
    mapper = getattr(model_class, '__mapper__', None)
    if mapper is None:
        return False
    return any(col.name in _SOFT_DELETE_COLUMNS for col in mapper.columns)


def _get_soft_delete_column(model_class):
    """Return the soft-delete column if it exists."""
    mapper = getattr(model_class, '__mapper__', None)
    if mapper is None:
        return None
    for col in mapper.columns:
        if col.name in _SOFT_DELETE_COLUMNS:
            return col
    return None


def _model_has_tenant_column(model_class) -> bool:
    """Check if the model class has a 'tenant_id' mapped column."""
    mapper = getattr(model_class, '__mapper__', None)
    return mapper is not None and 'tenant_id' in mapper.columns


def _check_bundle_limits_on_create(instance, tenant_id):
    """Enforce package max_users / max_patients via EntitlementResolver."""
    from app.core.saas.resolver import EntitlementResolver

    table = instance.__tablename__
    if table == 'users':
        current_count = db.session.execute(
            db.text('SELECT COUNT(*) FROM users WHERE tenant_id = :tid'),
            {'tid': tenant_id},
        ).scalar() or 0
        ok, _ = EntitlementResolver.check_limit(tenant_id, 'max_users', current_count, increment=1)
        if not ok:
            cap = EntitlementResolver.get_limit(tenant_id, 'max_users')
            raise ValueError(f"Bundle limit exceeded: maximum {cap} users allowed")
    elif table == 'patients':
        current_count = db.session.execute(
            db.text('SELECT COUNT(*) FROM patients WHERE tenant_id = :tid'),
            {'tid': tenant_id},
        ).scalar() or 0
        ok, _ = EntitlementResolver.check_limit(tenant_id, 'max_patients', current_count, increment=1)
        if not ok:
            cap = EntitlementResolver.get_limit(tenant_id, 'max_patients')
            raise ValueError(f"Bundle limit exceeded: maximum {cap} patients allowed")


# ---------------------------------------------------------------------------
# 1. AUTO-FILTER — every SELECT gets WHERE tenant_id = :tenant_id
# ---------------------------------------------------------------------------

@event.listens_for(Query, "before_compile", retval=True)
def tenant_filter_query(query):
    """Automatically append tenant_id filter to all multi-tenant queries."""
    session = getattr(query, 'session', None)
    tid = _current_tenant_id(session=session)
    if tid is None:
        if _is_saas_mode() and not _is_tenant_bypass():
            for desc in query.column_descriptions:
                entity = desc.get('entity')
                if entity is None or not isinstance(entity, type):
                    continue
                if _skip_table(entity):
                    continue
                if _model_has_tenant_column(entity):
                    raise TenantIsolationError(
                        f"Fail-closed: query on tenant-scoped model "
                        f"{entity.__name__} without tenant context in SaaS mode"
                    )
        return query

    # SQLAlchemy disallows adding filters after LIMIT/OFFSET have been applied.
    # Capture and temporarily remove them, inject tenant filters, then restore.
    limit_clause = getattr(query, '_limit_clause', None)
    offset_clause = getattr(query, '_offset_clause', None)
    if limit_clause is not None or offset_clause is not None:
        query = query.limit(None).offset(None)

    for desc in query.column_descriptions:
        entity = desc.get('entity')
        if entity is None or not isinstance(entity, type):
            continue
        if _skip_table(entity):
            continue
        if _model_has_tenant_column(entity):
            query = query.filter(entity.tenant_id == tid)
        # Soft-delete filter: exclude soft-deleted records
        if _model_has_soft_delete(entity):
            soft_col = _get_soft_delete_column(entity)
            if soft_col is not None:
                # For datetime columns: deleted_at IS NULL
                # For boolean columns: is_deleted = False
                col_type = str(soft_col.type).lower()
                if 'datetime' in col_type or 'timestamp' in col_type or 'date' in col_type:
                    query = query.filter(soft_col.is_(None))
                elif 'boolean' in col_type or 'bool' in col_type:
                    query = query.filter(soft_col == False)
                else:
                    query = query.filter(soft_col.is_(None))

    if limit_clause is not None:
        query = query.limit(limit_clause)
    if offset_clause is not None:
        query = query.offset(offset_clause)

    return query


# ---------------------------------------------------------------------------
# 1b. RLS CONTEXT — re-assert SET LOCAL before every ORM statement
#     A prior commit in the same session clears the transaction-scoped
#     SET LOCAL app.tenant_id variable.  Without re-assertion, subsequent
#     lazy-loads, column-refreshes, and ORM-level INSERT/UPDATE/DELETE
#     would fail the RLS USING / WITH CHECK because
#     current_setting('app.tenant_id', true) returns NULL.
# ---------------------------------------------------------------------------

@event.listens_for(OrmSession, 'do_orm_execute')
def tenant_filter_select(orm_execute_state):
    """Tenant filter for ``session.execute(select(...))`` style queries.

    In SQLAlchemy 2.0 the legacy ``Query.before_compile`` event only fires for
    ``session.query(...)`` calls.  New-style ``session.execute(select(...))``
    bypasses it entirely, so tenant isolation is not enforced for those queries.
    This handler replicates the same filtering for ORM SELECT statements
    executed via the 2.0-style ``select()`` API.

    For old-style ``session.query(...)`` calls the ``before_compile`` handler
    already applied the filter; we skip those to avoid double-filtering.
    """
    if not orm_execute_state.is_select:
        return

    statement = orm_execute_state.statement

    # Only intercept new-style Select objects; old-style Query objects are
    # already handled by the before_compile listener above.
    from sqlalchemy import Select as _SASelect
    if not isinstance(statement, _SASelect):
        return

    session = orm_execute_state.session
    tid = _current_tenant_id(session=session)
    if tid is None or _is_tenant_bypass():
        return

    # Skip internal SA ORM operations (identity-key reloads after commit,
    # lazy-loads, eager-loads).  These carry ``_sa_orm_load_options`` in
    # execution options and are triggered transparently when accessing
    # expired attributes on already-loaded objects.  Filtering them would
    # break users with NULL tenant_id (platform/owner) whose identity
    # reload query returns no rows, causing ObjectDeletedError.
    if "_sa_orm_load_options" in orm_execute_state.execution_options:
        return

    modified = False
    for desc in getattr(statement, 'column_descriptions', []):
        entity = desc.get('entity')
        if entity is None or not isinstance(entity, type):
            continue
        if _skip_table(entity):
            continue
        if _model_has_tenant_column(entity):
            statement = statement.filter(entity.tenant_id == tid)
            modified = True
        if _model_has_soft_delete(entity):
            soft_col = _get_soft_delete_column(entity)
            if soft_col is not None:
                col_type = str(soft_col.type).lower()
                if 'datetime' in col_type or 'timestamp' in col_type or 'date' in col_type:
                    statement = statement.filter(soft_col.is_(None))
                elif 'boolean' in col_type or 'bool' in col_type:
                    statement = statement.filter(soft_col == False)
                else:
                    statement = statement.filter(soft_col.is_(None))
                modified = True

    if modified:
        orm_execute_state.statement = statement


@event.listens_for(OrmSession, 'do_orm_execute')
def reassert_set_local(orm_execute_state):
    """Re-assert SET LOCAL app.tenant_id before every ORM statement.

    Catches lazy-loads triggered by expired-attribute access after a
    prior commit, where ``before_flush`` does not fire (no flush occurs
    for a plain SELECT).
    """
    # Skip raw text clauses to avoid recursive dispatch —
    # our own session.execute(db.text("SET LOCAL …")) triggers
    # do_orm_execute, which would re-enter this handler.
    if isinstance(orm_execute_state.statement, TextClause):
        return

    tid = _current_tenant_id(session=orm_execute_state.session)
    # SET LOCAL is PostgreSQL-specific; skip on SQLite etc.
    dialect = getattr(db.engine, 'dialect', None)
    if dialect is None or dialect.name != 'postgresql':
        return
    if tid is None:
        # No tenant context — explicitly clear any stale GUC so that
        # RLS policies see a clean state (empty string means "no tenant"
        # and will not match any tenant_id since they're positive ints).
        try:
            orm_execute_state.session.execute(db.text("SET LOCAL app.tenant_id = ''"))
        except Exception:
            logger.exception('RESET app.tenant_id failed in reassert_set_local')
            raise TenantIsolationError(
                'RESET app.tenant_id failed: tenant context cannot be cleared'
            )
        return
    try:
        orm_execute_state.session.execute(
            db.text(f"SET LOCAL app.tenant_id = '{tid}'"),
        )
    except Exception:
        logger.exception(
            'SET LOCAL app.tenant_id = %s failed in reassert_set_local', tid,
        )
        raise TenantIsolationError(
            'SET LOCAL re-assertion failed: tenant context cannot be '
            f'applied (tenant_id={tid})'
        )


# ---------------------------------------------------------------------------
# 2. AUTO-ASSIGN — every INSERT gets tenant_id = g.tenant_id
# ---------------------------------------------------------------------------

@event.listens_for(db.session.__class__, 'before_flush')
def auto_assign_tenant(session, flush_context, instances):
    """Auto-assign tenant_id to newly created records before flush.

    Ticket 5: Background jobs and tenant context fail-closed.
    When no tenant context is available, tenant-scoped records (models with
    tenant_id that are NOT in the global-model allowlist) must NOT silently
    persist with tenant_id=NULL. Only explicitly documented global models
    may be created without tenant context.
    """
    tid = _current_tenant_id(session=session)
    if tid is None:
        # Fail-closed: any tenant-scoped new record without explicit tenant_id
        # must raise an error, unless it is a proven global model or bypass is active.
        if not _is_tenant_bypass():
            for instance in session.new:
                mapper = getattr(instance, '__mapper__', None)
                if mapper is None:
                    continue
                if 'tenant_id' not in mapper.columns:
                    continue
                if _skip_table(instance.__class__):
                    continue
                if getattr(instance, 'tenant_id', None) is None:
                    raise TenantIsolationError(
                        f"Tenant-scoped record {instance.__class__.__name__} created without tenant context"
                    )
        return

    # Re-assert SET LOCAL — the previous transaction's commit (if any) cleared it,
    # so the RLS WITH CHECK on the coming INSERT would see NULL and fail.
    # Only applies to PostgreSQL; skip on SQLite etc.
    dialect = getattr(db.engine, 'dialect', None)
    if dialect is not None and dialect.name == 'postgresql':
        try:
            session.execute(db.text(f"SET LOCAL app.tenant_id = '{tid}'"))
        except Exception:
            logger.exception(
                'SET LOCAL app.tenant_id = %s failed in auto_assign_tenant', tid,
            )
            raise TenantIsolationError(
                'SET LOCAL re-assertion during flush failed: tenant context '
                f'cannot be applied (tenant_id={tid})'
            )

    for instance in session.new:
        mapper = getattr(instance, '__mapper__', None)
        if mapper is None:
            continue
        if 'tenant_id' not in mapper.columns:
            continue
        if _skip_table(instance.__class__):
            continue
        if getattr(instance, 'tenant_id', None) is None:
            instance.tenant_id = tid
        # Enforce bundle limits after tenant_id assignment (skip if bypass)
        if not _is_tenant_bypass() and instance.__tablename__ in ('users', 'patients'):
            _check_bundle_limits_on_create(instance, tid)


# ---------------------------------------------------------------------------
# 3. CROSS-TENANT GUARD — prevent UPDATE/DELETE across tenants
# ---------------------------------------------------------------------------

def _cross_tenant_check(session, is_delete=False):
    """Guard against cross-tenant UPDATE/DELETE on dirty/deleted objects."""
    if _is_tenant_bypass():
        return  # platform-level or background worker with explicit bypass
    tid = _current_tenant_id(session=session)
    if tid is None:
        return  # super-admin or single-tenant — skip

    target = session.deleted if is_delete else session.dirty
    for instance in target:
        mapper = getattr(instance, '__mapper__', None)
        if mapper is None:
            continue
        if 'tenant_id' not in mapper.columns:
            continue
        if _skip_table(instance.__class__):
            continue
        instance_tid = getattr(instance, 'tenant_id', None)
        if instance_tid is not None and instance_tid != tid:
            raise PermissionError(
                f"Cross-tenant {is_delete and 'DELETE' or 'UPDATE'} blocked: "
                f"{instance.__class__.__name__} (tenant={instance_tid}) "
                f"does not belong to current tenant (tenant={tid})"
            )


def _check_bundle_limits_on_update(instance, tenant_id):
    """Check max_users/max_patients when reactivating User or Patient."""
    from app.core.saas.resolver import EntitlementResolver

    table = instance.__tablename__
    if table == 'users':
        current_count = db.session.execute(
            db.text('SELECT COUNT(*) FROM users WHERE tenant_id = :tid'),
            {'tid': tenant_id},
        ).scalar() or 0
        ok, _ = EntitlementResolver.check_limit(tenant_id, 'max_users', current_count)
        if not ok:
            cap = EntitlementResolver.get_limit(tenant_id, 'max_users')
            raise ValueError(f"Bundle limit exceeded: maximum {cap} users allowed")
    elif table == 'patients':
        current_count = db.session.execute(
            db.text('SELECT COUNT(*) FROM patients WHERE tenant_id = :tid'),
            {'tid': tenant_id},
        ).scalar() or 0
        ok, _ = EntitlementResolver.check_limit(tenant_id, 'max_patients', current_count)
        if not ok:
            cap = EntitlementResolver.get_limit(tenant_id, 'max_patients')
            raise ValueError(f"Bundle limit exceeded: maximum {cap} patients allowed")


@event.listens_for(db.session.__class__, 'before_flush')
def cross_tenant_guard(session, flush_context, instances):
    """Prevent cross-tenant UPDATE/DELETE in the same before_flush.

    This runs after auto_assign_tenant in the same flush cycle.
    The check order matters: we first assign tenant_id to new objects,
    then verify existing objects belong to the current tenant.
    Also checks bundle limits on dirty User/Patient objects.
    """
    _cross_tenant_check(session, is_delete=False)
    _cross_tenant_check(session, is_delete=True)

    # Check bundle limits on dirty (updated) User/Patient instances (skip if bypass)
    if not _is_tenant_bypass():
        tid = _current_tenant_id(session=session)
        if tid is not None:
            for instance in session.dirty:
                if instance.__tablename__ in ('users', 'patients'):
                    _check_bundle_limits_on_update(instance, tid)


def register_tenant_listeners():
    """Idempotent registration of all tenant isolation listeners.
    All listeners are registered via @event.listens_for decorators above.
    This function exists for explicit documentation and testing.
    """
    pass
