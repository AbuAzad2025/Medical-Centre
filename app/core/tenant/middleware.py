"""
Tenant Resolution Middleware
Resolves tenant from subdomain, path, or dedicated domain.
"""
from flask import current_app, request, g
from app.core.tenant.models import Tenant

class TenantResolutionError(Exception):
    pass

def resolve_tenant() -> Tenant | None:
    """Resolve current tenant from request context."""
    if not current_app.config.get('ENABLE_SAAS_MODE', False):
        return None

    modes = {
        item.strip().lower()
        for item in str(current_app.config.get('TENANT_RESOLUTION_MODE', 'domain')).split(',')
        if item.strip()
    }
    if 'all' in modes:
        modes = {'path', 'subdomain', 'domain'}

    host = (request.headers.get('Host', '') or '').split(':', 1)[0].lower()
    path = request.path

    # 1. Path-based: /t/<slug>/
    if 'path' in modes and path.startswith('/t/'):
        slug = path.split('/')[2]
        return Tenant.query.filter_by(slug=slug, status='active').first()

    # 2. Subdomain: tenant.example.com
    base_domain = current_app.config.get('TENANT_BASE_DOMAIN')
    if 'subdomain' in modes and base_domain and host.endswith(f'.{base_domain}'):
        slug = host.replace(f'.{base_domain}', '')
        return Tenant.query.filter_by(subdomain=slug, status='active').first()

    # 3. Dedicated domain
    if 'domain' in modes and host:
        tenant = Tenant.query.filter_by(domain=host, status='active').first()
        if tenant:
            return tenant

    # 4. Fallback: default tenant (single-tenant mode or first active)
    return None

def set_tenant_context():
    """Flask before_request handler."""
    if not current_app.config.get('ENABLE_SAAS_MODE', False):
        g.current_tenant = None
        g.tenant_id = None
        return

    tenant = resolve_tenant()
    if tenant is None:
        raise TenantResolutionError("Tenant could not be resolved for SaaS request.")
    if tenant and not tenant.is_active_and_paid():
        raise TenantResolutionError("Tenant subscription expired or suspended.")
    g.current_tenant = tenant
    g.tenant_id = tenant.id if tenant else None
