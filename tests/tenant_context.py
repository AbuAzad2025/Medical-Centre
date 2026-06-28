"""Test helpers for tenant context under SaaS RLS / fail-closed isolation."""
from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

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
    from app.core.tenant.models import Tenant
    from app.extensions import db

    with app.app_context():
        tenant = Tenant.query.filter_by(slug=DEFAULT_TEST_TENANT_SLUG).first()
        if tenant:
            return tenant
        tenant = Tenant(
            slug=DEFAULT_TEST_TENANT_SLUG,
            name='صيدلية الشفاء',
            contact_email='pharmacy@test.local',
            status='active',
            product_profile_code='standalone_pharmacy',
        )
        db.session.add(tenant)
        db.session.commit()
        return tenant


def bind_tenant_on_g(tenant, *, db_session=None) -> None:
    """Set Flask ``g`` tenant fields and optional PostgreSQL RLS session var."""
    from flask import g
    from sqlalchemy import text

    g.tenant_id = tenant.id
    g.current_tenant = tenant
    g.tenant_slug = tenant.slug
    if db_session is not None:
        try:
            db_session.execute(text(f"SET LOCAL app.tenant_id = '{tenant.id}'"))
        except Exception:
            pass


@contextmanager
def tenant_test_context(app: Flask, tenant=None, *, bypass: bool = False):
    """Establish tenant context for DB operations in SaaS mode tests."""
    from flask import g
    from sqlalchemy import text

    from app.extensions import db

    with app.test_request_context():
        if bypass:
            g._tenant_filter_bypass = True
        elif tenant is not None:
            bind_tenant_on_g(tenant, db_session=db.session)
        yield g
