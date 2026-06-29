"""
Tenant-aware background job utilities.

All background workers must process one tenant at a time and enforce
 tenant_id on every tenant-scoped query.
"""
from __future__ import annotations

import functools
import logging
from typing import Callable, Optional, TypeVar

from flask import Flask

T = TypeVar('T')

_flask_app: Optional[Flask] = None


def bind_flask_app(app: Flask) -> None:
    """Store the Flask app used by Celery workers and tenant_task wrappers."""
    global _flask_app
    _flask_app = app


def get_flask_app() -> Optional[Flask]:
    return _flask_app


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


def with_tenant_context(app: Flask, tenant_id: int, job: Callable[[], T]) -> Optional[T]:
    """Run ``job()`` inside an app context scoped to ``tenant_id``.

    Binds full tenant context (including PostgreSQL RLS session var).
    Returns the job result, or None when the tenant does not exist.
    """
    from flask import g, has_app_context

    def _run_scoped() -> Optional[T]:
        from app.core.tenant.middleware import bind_g_tenant
        from app.core.tenant.models import Tenant

        tenant = Tenant.query.get(tenant_id)
        if tenant is None:
            return None
        bind_g_tenant(tenant)
        try:
            return job()
        finally:
            for key in ('tenant_id', 'current_tenant', 'tenant_slug', '_tenant_filter_bypass'):
                try:
                    g.pop(key, None)
                except Exception:
                    pass

    if has_app_context():
        return _run_scoped()
    with app.app_context():
        return _run_scoped()


def tenant_task(tenant_id_param: str = 'tenant_id'):
    """Decorator that wraps a callable in ``with_tenant_context`` when tenant_id is set."""

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            tenant_id = kwargs.get(tenant_id_param)
            app = get_flask_app()
            if app is None:
                from flask import current_app
                app = current_app._get_current_object()

            def _run():
                return fn(*args, **kwargs)

            if tenant_id is not None:
                return with_tenant_context(app, tenant_id, _run)
            return _run()

        return wrapper

    return decorator
