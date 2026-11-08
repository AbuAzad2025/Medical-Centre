"""Shared helper: build an isolated tenant for exact-count analytics tests.

The session-shared default tenant (pharmacy-shifa) accumulates rows from any
HTTP test that does not ask for ``rollback_db``, so exact-count assertions
against it are only stable by luck of runner order. Tests that need exact
counts create their own tenant instead; the shared tenant stays untouched.
"""

from __future__ import annotations

import uuid

import pytest


@pytest.fixture
def isolated_tenant(app, db):
    from flask import g

    from app.core.module.registry import get_all_module_names
    from app.core.tenant.models import Tenant
    from app.extensions import db as _db
    from tests.tenant_context import activate_tenant_modules, bind_tenant_on_g

    prev = g.get('_tenant_filter_bypass', False)
    g._tenant_filter_bypass = True
    slug = f'iso-{uuid.uuid4().hex[:12]}'
    try:
        t = Tenant(
            slug=slug,
            name=f'Isolated {slug}',
            contact_email=f'{slug}@test.local',
            status='ACTIVE',
            product_profile_code='multi_department_center',
        )
        _db.session.add(t)
        _db.session.flush()
        tenant_id = t.id
        _db.session.commit()
    finally:
        g._tenant_filter_bypass = prev

    activate_tenant_modules(app, t, get_all_module_names())
    tenant = _db.session.get(Tenant, tenant_id)
    bind_tenant_on_g(tenant, db_session=_db.session)
    return tenant
