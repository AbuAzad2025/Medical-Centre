"""
Tenant-aware background job utilities.

All background workers must process one tenant at a time and enforce
 tenant_id on every tenant-scoped query.
"""
from __future__ import annotations

import logging
from typing import Callable

from flask import Flask


def for_each_tenant(app: Flask, job: Callable[[int], None]) -> None:
    """Run ``job(tenant_id)`` inside a fresh app context for every active tenant.

    This helper guarantees that a background worker never operates across
    tenants. The caller passes a callable that receives the tenant id and is
    responsible for scoping all of its queries to that tenant.
    """
    with app.app_context():
        from app.core.tenant.models import Tenant, TenantStatus

        try:
            active_tenants = (
                Tenant.query.filter(Tenant.status == TenantStatus.ACTIVE)
                .order_by(Tenant.id)
                .with_entities(Tenant.id)
                .all()
            )
        except Exception:
            logging.exception("Failed to load active tenants for background job")
            return

        for (tenant_id,) in active_tenants:
            try:
                with app.app_context():
                    job(tenant_id)
            except Exception:
                logging.exception(f"Background job failed for tenant {tenant_id}")


def with_tenant_context(app: Flask, tenant_id: int, job: Callable[[], None]) -> None:
    """Run ``job()`` inside an app context scoped to ``tenant_id``.

    The tenant id is pushed to ``g.tenant_id`` so downstream services can
    enforce tenant scoping without threading current_user.
    """
    with app.app_context():
        from flask import g

        g.tenant_id = tenant_id
        try:
            job()
        finally:
            try:
                del g.tenant_id
            except AttributeError:
                pass
