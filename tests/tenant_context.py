"""Test helpers for tenant context under SaaS RLS / fail-closed isolation."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC
from typing import TYPE_CHECKING

from sqlalchemy import select
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
        try:
            g.pop(key, None)
        except Exception:
            pass


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
    if db_session is not None:
        try:
            db_session.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))
        except Exception:
            pass

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
    resp = client.post(
        '/auth/login',
        data={
            'username': user.username,
            'password': password,
            'tenant_slug': slug,
        },
    )
    tid = getattr(user, 'tenant_id', None) or getattr(tenant, 'id', None)
    version = int(getattr(user, 'session_version', 0) or 0)
    user_id = f'{user.id}:{version}'
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
        yield g
