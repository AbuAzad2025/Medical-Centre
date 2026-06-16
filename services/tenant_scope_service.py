"""
TenantScopeService — enforce tenant data isolation in queries
"""
from flask import g, current_app
from sqlalchemy import Column


class TenantScopeService:
    @staticmethod
    def filter_by_tenant(query, tenant_id_col: Column | str = 'tenant_id'):
        tenant_id = getattr(g, 'tenant_id', None)
        if tenant_id is not None:
            col = tenant_id_col if isinstance(tenant_id_col, str) else tenant_id_col.key
            return query.filter(getattr(query.model, col) == tenant_id)
        if current_app.config.get('ENABLE_SAAS_MODE', False):
            from flask import abort
            abort(403, description="Tenant context required in SaaS mode")
        return query

    @staticmethod
    def current_tenant_id() -> int | None:
        return getattr(g, 'tenant_id', None)

    @staticmethod
    def is_cross_tenant_allowed() -> bool:
        user = getattr(g, 'current_user', None)
        if user and user.role in ('super_admin', 'owner'):
            return True
        return False

    @staticmethod
    def assert_tenant_access(record):
        tenant_id = getattr(g, 'tenant_id', None)
        if tenant_id is None:
            return
        record_tenant = getattr(record, 'tenant_id', None)
        if record_tenant and record_tenant != tenant_id:
            from flask import abort
            abort(403, description="Cross-tenant access denied")