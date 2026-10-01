"""Test helpers for tenant context under SaaS RLS / fail-closed isolation."""

from __future__ import annotations

from contextlib import contextmanager, suppress
from datetime import UTC
from typing import TYPE_CHECKING

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.extensions import db

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
                    status='active',
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
                            status='active',
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
    """Establish tenant context for DB operations in SaaS mode tests."""
    from flask import g

    from app.extensions import db

    with app.test_request_context():
        if bypass:
            g._tenant_filter_bypass = True
        elif tenant is not None:
            bind_tenant_on_g(tenant, db_session=db.session)
            # Pin the GUC for the connection, not just the transaction. A
            # request-scoped helper (the layout's entitlement banner snapshots
            # usage) commits mid-request, and SET LOCAL dies with that commit;
            # the next ORM statement is then re-asserted from a cleared
            # context, RESETs the GUC, and every tenant-scoped refresh fails
            # with ObjectDeletedError on a row that is present.
            _pin_tenant_guc(getattr(tenant, 'id', tenant))
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


def create_scoped(app: Flask, tenant, obj):
    """Add *obj* and commit, inside *tenant*'s RLS scope, and return it.

    The shape that every fixture building a tenant-scoped row had grown by hand.
    ``users``, ``medications``, ``visits`` and the rest carry a WITH CHECK
    policy, so a row naming a tenant other than the bound one is rejected with
    InsufficientPrivilege — and whether it was accepted used to depend on which
    test ran before it, because the pooled connection keeps whatever tenant GUC
    it last carried.
    """
    with tenant_test_context(app, tenant):
        _pin_tenant_guc(getattr(tenant, 'id', tenant))
        db.session.add(obj)
        db.session.commit()
    return obj
