"""
Tenant-scoped database lookup helpers.

Centralizes the pattern of verifying that a fetched record belongs to the
current tenant context before returning it. Any lookup that fails the tenant
check raises PermissionError so cross-tenant access cannot be silently ignored.
"""

from __future__ import annotations

from flask import g
from sqlalchemy.orm import DeclarativeMeta

from app_factory import db


class TenantContextError(PermissionError):
    """Raised when a record is missing or belongs to another tenant."""
    pass


def get_tenant_record(
    model: type[DeclarativeMeta],
    record_id: int,
    tenant_id: int | None = None,
    *,
    error_message: str = "Unauthorized tenant context",
) -> DeclarativeMeta:
    """
    Fetch a single record by primary key and enforce tenant ownership.

    Args:
        model: SQLAlchemy model class (must expose `id` and `tenant_id` when
            tenant scoping is requested).
        record_id: Primary key value to look up.
        tenant_id: Explicit tenant id. If omitted, `g.tenant_id` is used.
        error_message: Message for the raised PermissionError on failure.

    Returns:
        The matching model instance.

    Raises:
        TenantContextError: If the record does not exist or does not belong to
            the active tenant context.
    """
    context_tenant_id = getattr(g, "tenant_id", None)

    # Ticket 3: g.tenant_id is authoritative for ordinary tenant-scoped requests.
    # An explicit tenant_id parameter must match g.tenant_id; if it conflicts
    # or if g.tenant_id is absent, fail closed.  No generic bypass flag is added.
    # Future platform tenant assumption will use a separate audited mechanism (MC-005).
    if context_tenant_id is not None:
        if tenant_id is not None and tenant_id != context_tenant_id:
            raise TenantContextError(error_message)
        resolved_tenant_id = context_tenant_id
    else:
        if tenant_id is not None:
            raise TenantContextError(error_message)
        resolved_tenant_id = None

    # If the model supports tenant scoping but no tenant context is available,
    # fail closed rather than returning a cross-tenant record.
    if resolved_tenant_id is None and hasattr(model, "tenant_id"):
        raise TenantContextError(error_message)

    # Always fetch via db.session.get first so test monkeypatches and
    # SQLAlchemy session proxies work identically to the original code.
    record = db.session.get(model, record_id)

    if record is None:
        raise TenantContextError(error_message)

    # If a tenant context is active and the model supports tenant scoping,
    # enforce ownership.
    if resolved_tenant_id is not None and hasattr(model, "tenant_id"):
        if getattr(record, "tenant_id", None) != resolved_tenant_id:
            raise TenantContextError(error_message)

    return record


def tenant_filter(model: type[DeclarativeMeta], tenant_id: int | None = None):
    """
    Return a base query scoped to the active tenant.

    Useful when the caller needs to apply additional filters beyond a simple
    primary-key lookup.
    """
    resolved_tenant_id = tenant_id if tenant_id is not None else getattr(g, "tenant_id", None)
    q = model.query
    if resolved_tenant_id is not None and hasattr(model, "tenant_id"):
        q = q.filter(model.tenant_id == resolved_tenant_id)
    return q
