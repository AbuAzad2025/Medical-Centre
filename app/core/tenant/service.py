"""
Tenant Context Service
Provides helpers for tenant-scoped queries and validation.
"""
from flask import g
from app.core.tenant.models import Tenant
from app.extensions import db

class TenantContextService:
    """Thread-safe tenant context utilities."""

    @staticmethod
    def get_current_tenant() -> Tenant | None:
        return getattr(g, 'current_tenant', None)

    @staticmethod
    def get_current_tenant_id() -> int | None:
        return getattr(g, 'tenant_id', None)

    @staticmethod
    def tenant_filter(query, model_cls):
        """Apply tenant_id filter to a query if the model has tenant_id."""
        tenant_id = TenantContextService.get_current_tenant_id()
        if tenant_id and hasattr(model_cls, 'tenant_id'):
            return query.filter(model_cls.tenant_id == tenant_id)
        return query

    @staticmethod
    def apply_to_model(instance):
        """Auto-assign tenant_id to a model instance before commit."""
        tenant_id = TenantContextService.get_current_tenant_id()
        if tenant_id and hasattr(instance, 'tenant_id'):
            instance.tenant_id = tenant_id

    @staticmethod
    def ensure_tenant_active(tenant: Tenant | None = None):
        t = tenant or TenantContextService.get_current_tenant()
        if not t:
            raise PermissionError("No tenant context found.")
        if not t.is_active_and_paid():
            raise PermissionError("Tenant is not active or subscription expired.")
