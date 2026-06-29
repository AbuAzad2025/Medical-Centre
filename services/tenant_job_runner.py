"""
Tenant-aware background job utilities.

All background workers must process one tenant at a time and enforce
 tenant_id on every tenant-scoped query.
"""
from __future__ import annotations

import logging
from typing import Callable

from flask import Flask


def _operational_tenant_statuses():
    from app.shared.enums import TenantStatus

    return (TenantStatus.ACTIVE, TenantStatus.TRIAL)


def for_each_tenant(app: Flask, job: Callable[[int], None]) -> None:
    """Run ``job(tenant_id)`` inside a fresh app context for every active tenant.

    Includes TRIAL tenants so reminders and notifications work during trial.
    """
    with app.app_context():
        from app.core.tenant.models import Tenant

        try:
            active_tenants = (
                Tenant.query.filter(Tenant.status.in_(_operational_tenant_statuses()))
                .order_by(Tenant.id)
                .with_entities(Tenant.id)
                .all()
            )
        except Exception:
            logging.exception("Failed to load active tenants for background job")
            return

        for (tenant_id,) in active_tenants:
            try:
                with_tenant_context(app, tenant_id, lambda: job(tenant_id))
            except Exception:
                logging.exception(f"Background job failed for tenant {tenant_id}")


def with_tenant_context(app: Flask, tenant_id: int, job: Callable[[], None]) -> None:
    """Run ``job()`` inside an app context scoped to ``tenant_id``.

    Binds full tenant context (including PostgreSQL RLS session var).
    """
    with app.app_context():
        from app.core.tenant.middleware import bind_g_tenant
        from app.core.tenant.models import Tenant
        from app.extensions import db
        from flask import g

        tenant = Tenant.query.get(tenant_id)
        if tenant is None:
            return
        bind_g_tenant(tenant, db_session=db.session)
        try:
            job()
        finally:
            for key in ('tenant_id', 'current_tenant', 'tenant_slug', '_tenant_filter_bypass'):
                try:
                    g.pop(key, None)
                except Exception:
                    pass
