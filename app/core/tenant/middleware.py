"""
Tenant Resolution Middleware
Resolves tenant from subdomain, path, or dedicated domain.
"""
from flask import request, g
from app.core.tenant.models import Tenant

class TenantResolutionError(Exception):
    pass

def resolve_tenant() -> Tenant | None:
    """Resolve current tenant from request context."""
    host = request.headers.get('Host', '')
    path = request.path

    # 1. Path-based: /t/<slug>/
    if path.startswith('/t/'):
        slug = path.split('/')[2]
        return Tenant.query.filter_by(slug=slug, status='active').first()

    # 2. Subdomain: tenant.azad.com
    base_domain = 'azad.com'  # configurable
    if host.endswith(f'.{base_domain}'):
        slug = host.replace(f'.{base_domain}', '')
        return Tenant.query.filter_by(subdomain=slug, status='active').first()

    # 3. Dedicated domain
    tenant = Tenant.query.filter_by(domain=host, status='active').first()
    if tenant:
        return tenant

    # 4. Fallback: default tenant (single-tenant mode or first active)
    return None

def set_tenant_context():
    """Flask before_request handler."""
    tenant = resolve_tenant()
    if tenant and not tenant.is_active_and_paid():
        raise TenantResolutionError("Tenant subscription expired or suspended.")
    g.current_tenant = tenant
    g.tenant_id = tenant.id if tenant else None
