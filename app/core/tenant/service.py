"""
Tenant Context Service
Provides helpers for tenant-scoped queries and validation.
"""

from flask import g

from app.core.tenant.models import Tenant


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
        tenant_id = TenantContextService.get_current_tenant_id()
        if tenant_id is not None and hasattr(model_cls, 'tenant_id'):
            return query.filter(model_cls.tenant_id == tenant_id)
        if hasattr(model_cls, 'tenant_id'):
            try:
                from flask import current_app

                if current_app.config.get('ENABLE_SAAS_MODE', False):
                    if not g.get('_tenant_filter_bypass', False):
                        raise PermissionError('No tenant context found.')
            except PermissionError:
                raise
            except Exception:
                pass
        return query

    @staticmethod
    def apply_to_model(instance):
        tenant_id = TenantContextService.get_current_tenant_id()
        if tenant_id is not None and hasattr(instance, 'tenant_id'):
            instance.tenant_id = tenant_id

    @staticmethod
    def ensure_tenant_active(tenant: Tenant | None = None):
        t = tenant or TenantContextService.get_current_tenant()
        if not t:
            raise PermissionError('No tenant context found.')
        if not t.is_active_and_paid():
            raise PermissionError('Tenant is not active or subscription expired.')

    @staticmethod
    def is_cross_tenant_allowed() -> bool:
        user = getattr(g, 'current_user', None)
        return bool(user and user.role in ('super_admin', 'owner'))

    @staticmethod
    def assert_tenant_access(record):
        tenant_id = TenantContextService.get_current_tenant_id()
        if tenant_id is None:
            try:
                from flask import current_app

                if current_app.config.get('ENABLE_SAAS_MODE', False):
                    if not g.get('_tenant_filter_bypass', False):
                        from flask import abort

                        abort(403, description='Cross-tenant access denied')
            except Exception as exc:
                if 'Cross-tenant' in str(exc):
                    raise
            return
        record_tenant = getattr(record, 'tenant_id', None)
        if record_tenant is not None and record_tenant != tenant_id:
            from flask import abort

            abort(403, description='Cross-tenant access denied')
