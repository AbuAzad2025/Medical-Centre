"""
Tenant Data Isolation Layer
Auto-injects tenant_id = g.tenant_id into every query/insert/update/delete.

Three hooks:
  1. before_compile (Query) — auto-filters SELECT queries
  2. before_flush (Session) — auto-assigns tenant_id on INSERT + bundle limit check
  3. before_update_delete (Session) — prevents cross-tenant UPDATE/DELETE
"""
from flask import g
from sqlalchemy import event
from sqlalchemy.orm import Query
from app.extensions import db


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _current_tenant_id():
    """Return tenant_id from Flask context, or None (super-admin / single-tenant)."""
    try:
        return g.get('tenant_id')
    except RuntimeError:
        return None


def _model_has_tenant_column(model_class) -> bool:
    """Check if the model class has a 'tenant_id' mapped column."""
    mapper = getattr(model_class, '__mapper__', None)
    return mapper is not None and 'tenant_id' in mapper.columns


def _skip_table(model_class) -> bool:
    """Tables that should NEVER be tenant-filtered (shared across tenants)."""
    name = getattr(model_class, '__tablename__', '')
    return name in {
        'tenants', 'subscription_plans', 'alembic_version',
        'module_definitions', 'notification_rules',
        'roles', 'permissions', 'role_permissions', 'user_permissions', 'module_permissions', 'department_permissions',
        'system_configs', 'branding_settings', 'system_themes',
        'icd10_codes', 'cpt_codes', 'drg_codes',
        'product_bundles', 'platform_audit_logs',
    }


def _check_bundle_limits_on_create(instance, tenant_id):
    """Enforce bundle max_users / max_patients limits when creating User or Patient."""
    from app.core.tenant.models import Tenant, get_bundle_for_profile
    t = Tenant.query.get(tenant_id)
    if t is None or not t.product_profile_code:
        return
    bundle = get_bundle_for_profile(t.product_profile_code)
    if bundle is None:
        return

    table = instance.__tablename__
    if table == 'users':
        current_count = db.session.execute(
            db.text('SELECT COUNT(*) FROM users WHERE tenant_id = :tid'),
            {'tid': tenant_id}
        ).scalar() or 0
        if bundle.max_users is not None and (current_count + 1) > bundle.max_users:
            raise ValueError(f"Bundle limit exceeded: maximum {bundle.max_users} users allowed")
    elif table == 'patients':
        current_count = db.session.execute(
            db.text('SELECT COUNT(*) FROM patients WHERE tenant_id = :tid'),
            {'tid': tenant_id}
        ).scalar() or 0
        if bundle.max_patients is not None and (current_count + 1) > bundle.max_patients:
            raise ValueError(f"Bundle limit exceeded: maximum {bundle.max_patients} patients allowed")


# ---------------------------------------------------------------------------
# 1. AUTO-FILTER — every SELECT gets WHERE tenant_id = :tenant_id
# ---------------------------------------------------------------------------

@event.listens_for(Query, "before_compile", retval=True)
def tenant_filter_query(query):
    """Automatically append tenant_id filter to all multi-tenant queries."""
    tid = _current_tenant_id()
    if tid is None:
        return query  # super-admin or single-tenant mode — skip

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

    if limit_clause is not None:
        query = query.limit(limit_clause)
    if offset_clause is not None:
        query = query.offset(offset_clause)

    return query


# ---------------------------------------------------------------------------
# 2. AUTO-ASSIGN — every INSERT gets tenant_id = g.tenant_id
# ---------------------------------------------------------------------------

@event.listens_for(db.session.__class__, 'before_flush')
def auto_assign_tenant(session, flush_context, instances):
    """Auto-assign tenant_id to newly created records before flush."""
    tid = _current_tenant_id()
    if tid is None:
        return

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
        # Enforce bundle limits after tenant_id assignment
        if instance.__tablename__ in ('users', 'patients'):
            _check_bundle_limits_on_create(instance, tid)


# ---------------------------------------------------------------------------
# 3. CROSS-TENANT GUARD — prevent UPDATE/DELETE across tenants
# ---------------------------------------------------------------------------

def _cross_tenant_check(session, is_delete=False):
    """Guard against cross-tenant UPDATE/DELETE on dirty/deleted objects."""
    tid = _current_tenant_id()
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
    """Check bundle max_users/max_patients limits when reactivating User or Patient."""
    from app.core.tenant.models import Tenant, get_bundle_for_profile
    t = Tenant.query.get(tenant_id)
    if t is None or not t.product_profile_code:
        return
    bundle = get_bundle_for_profile(t.product_profile_code)
    if bundle is None:
        return

    table = instance.__tablename__
    if table == 'users':
        if bundle.max_users is not None:
            current_count = db.session.execute(
                db.text('SELECT COUNT(*) FROM users WHERE tenant_id = :tid AND deleted_at IS NULL'),
                {'tid': tenant_id}
            ).scalar() or 0
            if current_count > bundle.max_users:
                raise ValueError(f"Bundle limit exceeded: maximum {bundle.max_users} users allowed")
    elif table == 'patients':
        if bundle.max_patients is not None:
            current_count = db.session.execute(
                db.text('SELECT COUNT(*) FROM patients WHERE tenant_id = :tid AND deleted_at IS NULL'),
                {'tid': tenant_id}
            ).scalar() or 0
            if current_count > bundle.max_patients:
                raise ValueError(f"Bundle limit exceeded: maximum {bundle.max_patients} patients allowed")


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

    # Check bundle limits on dirty (updated) User/Patient instances
    tid = _current_tenant_id()
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
