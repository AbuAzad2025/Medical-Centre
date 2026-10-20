"""Test helpers for tenant context under SaaS RLS / fail-closed isolation."""

from __future__ import annotations

from contextlib import contextmanager, suppress
from datetime import UTC
from typing import TYPE_CHECKING

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.shared.user_role_policy import normalize_role

if TYPE_CHECKING:
    from flask import Flask


_TENANT_G_KEYS = (
    'tenant_id',
    'current_tenant',
    'tenant_slug',
    '_tenant_filter_bypass',
    '_entitlement_cache',
    '_entitlement_limit_cache',
    '_entitlement_audit_seen',
)

DEFAULT_TEST_TENANT_SLUG = 'pharmacy-shifa'

# Ids of the shared test tenant(s) this session has created. Populated by
# ensure_default_test_tenant. Consumers must treat it as read-only.
SHARED_TEST_TENANT_IDS: set[int] = set()


def _sync_tenant_sequence() -> None:
    """Keep ``tenants.id`` sequence ahead of seeded rows in PostgreSQL tests."""
    try:
        db.session.execute(
            db.text(
                "SELECT setval(pg_get_serial_sequence('tenants','id'), "
                'COALESCE((SELECT MAX(id) FROM tenants), 1), true)'
            )
        )
        db.session.commit()
    except Exception:
        db.session.rollback()


def clear_tenant_g() -> None:
    """Remove tenant-related keys from Flask ``g`` (shared session app context in tests)."""
    from flask import g

    for key in _TENANT_G_KEYS:
        with suppress(Exception):
            g.pop(key, None)


def clear_tenant_context() -> None:
    """Drop *every* tenant binding, not only the Flask ``g`` ones.

    ``tenant_filter._current_tenant_id()`` consults the transaction-scoped
    ``session.info['_tenant_id']`` before ``g``, so clearing ``g`` alone leaves
    the request looking like it still has a tenant and the fail-closed guard
    stays silent. The ``db`` fixture rebinds that key on every single test, so a
    helper that only clears ``g`` is a silent no-op rather than an obvious one.

    Use this when the intent is "no tenant in scope at all"; use
    :func:`clear_tenant_g` when the intent is "no tenant on this request".
    """
    clear_tenant_g()
    with suppress(Exception):
        db.session.info.pop('_tenant_id', None)


def ensure_default_test_tenant(app: Flask):
    """Return (or create) the shared default tenant used by SaaS-mode tests."""
    from datetime import datetime

    from app.core.module.models import TenantModule
    from app.core.module.registry import get_all_module_names
    from app.core.tenant.models import Tenant
    from app.extensions import db

    with app.app_context(), app.test_request_context():
        from flask import g

        prev_bypass = g.get('_tenant_filter_bypass', False)
        g._tenant_filter_bypass = True
        try:
            tenant = (
                db.session.execute(select(Tenant).filter_by(slug=DEFAULT_TEST_TENANT_SLUG))
                .scalars()
                .first()
            )
            if not tenant:
                tenant = Tenant(
                    slug=DEFAULT_TEST_TENANT_SLUG,
                    name='صيدلية الشفاء',
                    contact_email='pharmacy@test.local',
                    status='ACTIVE',
                    product_profile_code='multi_department_center',
                )
                db.session.add(tenant)
                try:
                    db.session.commit()
                except IntegrityError:
                    db.session.rollback()
                    _sync_tenant_sequence()
                    tenant = (
                        db.session.execute(select(Tenant).filter_by(slug=DEFAULT_TEST_TENANT_SLUG))
                        .scalars()
                        .first()
                    )
                    if not tenant:
                        tenant = Tenant(
                            slug=DEFAULT_TEST_TENANT_SLUG,
                            name='صيدلية الشفاء',
                            contact_email='pharmacy@test.local',
                            status='ACTIVE',
                            product_profile_code='multi_department_center',
                        )
                        db.session.add(tenant)
                        db.session.commit()

            bind_tenant_on_g(tenant, db_session=db.session)
            # The writes below are interleaved with commits, and a SET LOCAL
            # binding dies with the transaction that carried the previous one.
            # Without a connection-level pin, the TenantModule inserts are
            # evaluated against an empty tenant GUC and the policy rejects
            # them — a failure that then depends on which test ran before this
            # one, because the pooled connection keeps whatever GUC it had.
            _pin_tenant_guc(tenant.id)

            # Ensure tenant has active payment status for module access
            from app.shared.enums import TenantStatus

            if tenant.status != TenantStatus.ACTIVE:
                tenant.status = TenantStatus.ACTIVE
                db.session.commit()

            now = datetime.now(UTC)
            changed = False
            for module_name in get_all_module_names():
                row = (
                    db.session.execute(
                        select(TenantModule).filter_by(tenant_id=tenant.id, module_name=module_name)
                    )
                    .scalars()
                    .first()
                )
                if row:
                    if not row.is_active:
                        row.is_active = True
                        row.activated_at = now
                        row.deactivated_at = None
                        changed = True
                else:
                    db.session.add(
                        TenantModule(
                            tenant_id=tenant.id,
                            module_name=module_name,
                            is_active=True,
                            activated_at=now,
                        )
                    )
                    changed = True
            if changed:
                db.session.commit()
            # Recorded so the conftest cap suppression can identify this tenant
            # without querying for it. An earlier version resolved the id lazily
            # from inside the patched get_limit, where the query has no reliable
            # context and its failure was swallowed -- so on the shards the
            # suppression silently never applied and the shared tenant kept its
            # 50-user package cap.
            SHARED_TEST_TENANT_IDS.add(tenant.id)
            return tenant
        finally:
            if prev_bypass:
                g._tenant_filter_bypass = True
            else:
                g.pop('_tenant_filter_bypass', None)


def bind_tenant_on_g(tenant, *, db_session=None) -> None:
    """Set Flask ``g`` tenant fields and optional PostgreSQL RLS session var."""
    from flask import g
    from sqlalchemy import text
    from sqlalchemy.orm import object_session

    from app.core.tenant.models import Tenant

    if isinstance(tenant, int):
        tenant_id = tenant
    elif tenant.__dict__.get('id') is not None:
        tenant_id = int(tenant.__dict__['id'])
    elif object_session(tenant) is not None:
        tenant_id = int(tenant.id)
    else:
        return

    bound = db_session.get(Tenant, tenant_id) if db_session is not None else None
    if bound is None:
        bound = db.session.get(Tenant, tenant_id)
    if bound is None:
        return

    g.tenant_id = tenant_id
    g.current_tenant = bound
    g.tenant_slug = bound.slug
    # session.info['_tenant_id'] too, and this is not cosmetic. It is the FIRST
    # source _current_tenant_id() consults (app/shared/tenant_filter.py:186), and
    # reassert_set_local re-asserts the GUC from it before every ORM statement —
    # so a stale value here silently overwrites the binding made one line above
    # and the next write is rejected as a cross-tenant row. Production's binder
    # sets it for the same reason (app/core/tenant/middleware.py:289).
    if db_session is not None:
        db_session.info['_tenant_id'] = tenant_id
    if db_session is not None:
        with suppress(Exception):
            db_session.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))

    # Set enabled_modules for module-scoped access control (mirrors middleware)
    try:
        from app.core.module.validators import get_active_modules_for_tenant

        g.enabled_modules = get_active_modules_for_tenant(tenant_id)
    except Exception:
        g.enabled_modules = set()


def reset_request_state() -> None:
    """Drop the per-request state a test request must not inherit.

    Under test the request reuses the conftest's app context, so ``g`` survives
    from the previous request — in production it dies with the request. Two
    entries matter and both were measured, not guessed:

    * ``g._login_user`` — Flask-Login's per-request user cache. Left over from a
      synthetic login, the next request authenticates with *that* instance
      instead of loading the user from the session cookie. The instance is
      expired (the fixture committed) and attached to no session, so the first
      attribute read raises ``ObjectDeletedError`` on a user that exists.
    * ``g.tenant_id`` — ``bind_tenant_from_session()`` returns early when ``g``
      already carries an id, so a stale value silently skips the session binding
      and the request runs against whichever tenant ``g`` happened to name while
      the connection GUC names another. The module guard then sees no active
      modules and answers 403.

    Every helper that fakes a login — this module's, and the ones hand-rolled in
    individual test files — must call this before the test issues its request.
    """
    from flask import g

    g.pop('_login_user', None)
    g.pop('tenant_id', None)


def login_test_client(client, user, tenant, password: str = 'ValidPass123!'):
    """POST /auth/login and ensure SaaS session carries tenant context."""
    from app.core.rate_limiter import _shared_store

    _shared_store.clear()
    slug = getattr(tenant, 'slug', None) or ''
    # Read everything off the user BEFORE the request. The request runs a full
    # before_request/teardown cycle, and its teardown clears app.tenant_id on
    # the shared connection. An expired attribute re-read after that point
    # goes through RLS with an empty tenant GUC, sees no row, and raises
    # ObjectDeletedError on an object that is still perfectly present.
    tid = getattr(user, 'tenant_id', None) or getattr(tenant, 'id', None)
    version = int(getattr(user, 'session_version', 0) or 0)
    user_id = f'{user.id}:{version}'
    resp = client.post(
        '/auth/login',
        data={
            'username': user.username,
            'password': password,
            'tenant_slug': slug,
        },
    )
    with client.session_transaction() as sess:
        sess['_user_id'] = user_id
        if tid is not None:
            sess['tenant_id'] = int(tid)
        if slug:
            sess['tenant_slug'] = slug
        sess['_fresh'] = True

    # The login request authenticated the *test's* user object; drop the
    # per-request state it left behind (see reset_request_state).
    reset_request_state()
    return resp


def ensure_test_user(
    db, tenant, *, username: str, role: str, password: str = 'ValidPass123!', **extra
):
    """Create or fetch a tenant-scoped user for SaaS-mode integration tests."""
    from flask import g

    from models.user import User

    prev_bypass = g.get('_tenant_filter_bypass', False)
    g._tenant_filter_bypass = True
    try:
        # Bind first. `users` carries a WITH CHECK policy, and the ORM bypass
        # does not reach the database: a row naming a tenant other than the
        # bound one is rejected with InsufficientPrivilege. Callers inside
        # `tenant_test_context` already have this, and re-binding is a no-op;
        # callers outside it were silently depending on whichever tenant the
        # pooled connection happened to carry.
        bind_tenant_on_g(tenant, db_session=db.session)
        _pin_tenant_guc(getattr(tenant, 'id', tenant))
        user = (
            db.session.execute(select(User).filter_by(username=username, tenant_id=tenant.id))
            .scalars()
            .first()
        )
        if not user:
            user = User(
                username=username,
                email=extra.get('email', f'{username}@test.local'),
                full_name=extra.get('full_name', username),
                role=role,
                is_active=True,
                tenant_id=tenant.id,
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
        elif (
            normalize_role(user.role) != normalize_role(role)
            or not user.is_active
            or int(getattr(user, 'session_version', 0) or 0) != 0
        ):
            # The role/session_version is part of what this helper promises, not a
            # hint. The test database persists between runs, so a username first
            # created under another role or with a bumped session_version came
            # back unchanged and the caller silently got someone the gate rejects.
            user.role = role
            user.is_active = True
            user.session_version = 0
            db.session.commit()
        return user
    finally:
        if prev_bypass:
            g._tenant_filter_bypass = True
        else:
            g.pop('_tenant_filter_bypass', None)


def _pin_tenant_guc(tenant_id: int) -> None:
    """Set ``app.tenant_id`` for the whole connection, not just one transaction.

    ``bind_tenant_on_g`` uses ``SET LOCAL``, which PostgreSQL discards at the
    next COMMIT. That is right for a request, where the binding is re-asserted
    per statement, but a helper that writes, commits, and then writes again
    would have its second write evaluated against an empty tenant GUC — and
    every RLS policy rejects the row. Session-level here, and deliberately
    narrow: only helpers that commit mid-way call it.
    """
    with suppress(Exception):
        db.session.execute(
            text('SELECT set_config(:k, :v, false)'),
            {'k': 'app.tenant_id', 'v': str(tenant_id)},
        )


def bind_platform_tenant(app: Flask):
    """Bind the platform tenant itself and return it.

    Uses ``seeds.production_baseline.platform_tenant_row`` (the ``platform``
    slug, else the lowest id) rather than ``platform_tenant_scope``, which
    resolves "whatever tenant is currently bound" first and would hand back an
    arbitrary tenant inside a test that already has one bound.
    """
    from flask import g

    from seeds.production_baseline import platform_tenant_row

    g._tenant_filter_bypass = True
    try:
        tenant = platform_tenant_row()
        if tenant is None:
            raise RuntimeError('no tenant row exists; the platform tenant cannot be bound')
        bind_tenant_on_g(tenant, db_session=db.session)
        _pin_tenant_guc(tenant.id)
        return tenant
    finally:
        g.pop('_tenant_filter_bypass', None)


@contextmanager
def tenant_test_context(app: Flask, tenant=None, *, bypass: bool = False):
    """Establish tenant context for DB operations in SaaS mode tests.

    The binding is restored on exit. ``bind_tenant_on_g`` writes
    ``db.session.info['_tenant_id']``, and that is the FIRST source
    ``_current_tenant_id()`` consults - so entering this context for a second
    tenant repointed the session at it, and the caller was left running as that
    tenant for every statement afterwards. A helper that changes the session's
    tenant has to put it back.
    """
    from flask import g

    from app.extensions import db

    with app.test_request_context():
        if bypass:
            g._tenant_filter_bypass = True
            yield g
        elif tenant is not None:
            previous_tenant_id = db.session.info.get('_tenant_id')
            try:
                bind_tenant_on_g(tenant, db_session=db.session)
                # Pin the GUC for the connection, not just the transaction. A
                # request-scoped helper (the layout's entitlement banner snapshots
                # usage) commits mid-request, and SET LOCAL dies with that commit;
                # the next ORM statement is then re-asserted from a cleared
                # context, RESETs the GUC, and every tenant-scoped refresh fails
                # with ObjectDeletedError on a row that is present.
                _pin_tenant_guc(getattr(tenant, 'id', tenant))
                yield g
            finally:
                # Restore the session's tenant. SET LOCAL in the restore is
                # transaction-scoped and takes precedence over the pinned
                # session-level SET for the rest of this transaction.
                if previous_tenant_id is not None:
                    bind_tenant_on_g(previous_tenant_id, db_session=db.session)
                else:
                    db.session.info.pop('_tenant_id', None)
        else:
            yield g


def activate_tenant_modules(app: Flask, tenant, module_names) -> None:
    """Activate *module_names* for *tenant*, inside that tenant's own scope.

    ``tenant_modules`` carries a WITH CHECK policy, so a row is only admissible
    while ``app.tenant_id`` names the same tenant. Naming ``tenant_id`` on the
    row is not enough: written from an unbound context the insert is rejected
    with InsufficientPrivilege. Every "build a tenant with a bundle" helper in
    the suite needs this, and each one had grown its own copy of the loop.

    Idempotent, and the existence check runs *inside* the scope on purpose:
    outside it the policy hides the existing rows, every name looks missing, and
    the insert then trips the unique constraint.
    """
    from app.core.module.models import TenantModule

    with tenant_test_context(app, tenant):
        pending = [
            name
            for name in module_names
            if (
                db.session.execute(
                    select(TenantModule).filter_by(tenant_id=tenant.id, module_name=name)
                )
                .scalars()
                .first()
                is None
            )
        ]
        for name in pending:
            db.session.add(TenantModule(tenant_id=tenant.id, module_name=name, is_active=True))
        if pending:
            db.session.commit()


def refresh_scoped(app: Flask, tenant, obj):
    """Re-read *obj* inside *tenant*'s RLS scope, and return it.

    A bare ``session.refresh(obj)`` run after a request is evaluated against
    whatever tenant is currently bound. For a row belonging to another tenant
    that returns nothing, and SQLAlchemy reports it as "could not refresh" or
    raises ObjectDeletedError on a row that is present. Read it where it lives.

    A detached instance is re-attached rather than merged. Merging would
    refresh a copy and leave the caller's object holding stale values, so an
    assertion about that object would pass without ever reading the row - the
    check would stop proving anything.
    """
    with tenant_test_context(app, tenant):
        if obj not in db.session:
            db.session.add(obj)
        db.session.expire(obj)
        db.session.refresh(obj)
    return obj


def create_scoped(app: Flask, tenant, obj):
    """Add *obj* and commit, inside *tenant*'s RLS scope, and return it.

    The shape that every fixture building a tenant-scoped row had grown by hand.
    ``users``, ``medications``, ``visits`` and the rest carry a WITH CHECK
    policy, so a row naming a tenant other than the bound one is rejected with
    InsufficientPrivilege — and whether it was accepted used to depend on which
    test ran before it, because the pooled connection keeps whatever tenant GUC
    it last carried.

    The object is returned detached, with its values loaded. The commit
    expires every attribute, and the caller holds the object after the scope
    has closed - so under the caller's tenant the row is invisible to this
    session and touching an expired attribute raises ObjectDeletedError on a
    row that is present. Loading the values here, while the scope still names
    the tenant that owns the row, means the caller can read them without a
    refresh.
    """
    with tenant_test_context(app, tenant):
        _pin_tenant_guc(getattr(tenant, 'id', tenant))
        db.session.add(obj)
        db.session.commit()
        # Load the values while the scope still names that tenant, then
        # detach so no later access can trigger a refresh under the wrong one.
        db.session.refresh(obj)
        db.session.expunge(obj)
    return obj
