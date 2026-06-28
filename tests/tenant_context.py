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


def clear_tenant_g() -> None:
    """Remove tenant-related keys from Flask ``g`` (shared session app context in tests)."""
    from flask import g

    for key in _TENANT_G_KEYS:
        try:
            g.pop(key, None)
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
            g.tenant_id = tenant.id
            g.current_tenant = tenant
            try:
                db.session.execute(text(f"SET LOCAL app.tenant_id = '{tenant.id}'"))
            except Exception:
                pass
        yield g
