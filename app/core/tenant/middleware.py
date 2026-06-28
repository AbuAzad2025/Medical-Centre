"""
Tenant Resolution Middleware
Resolves tenant from subdomain, path (/t/<slug>/), or dedicated domain.
Provides TenantPathWSGIMiddleware to rewrite /t/<slug>/... → /...
and set_tenant_context() as the Flask before_request handler.
"""
from flask import current_app, request, g
from app.core.tenant.models import Tenant


class TenantPathWSGIMiddleware:
    """WSGI middleware: rewrites /t/<slug>/<path> → /<path> before Flask routing.

    Stores the resolved slug in environ['tenant.slug'] for later use by
    set_tenant_context().
    """
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '').strip()
        if path.startswith('/t/'):
            parts = path.split('/')
            if len(parts) >= 3 and parts[2]:
                environ['tenant.slug'] = parts[2]
                environ['PATH_INFO'] = '/' + '/'.join(parts[3:])
                environ['RAW_URI'] = environ.get('RAW_URI', path).replace(
                    f'/t/{parts[2]}', '', 1
                )
        return self.app(environ, start_response)


class TenantResolutionError(Exception):
    pass


def _get_tenant_by_slug(slug: str) -> Tenant | None:
    """Return active tenant by slug, or None."""
    return Tenant.query.filter_by(slug=slug, status='active').first()


def _auto_create_default_tenant() -> Tenant | None:
    """Auto-create a default tenant if TENANT_AUTO_CREATE is enabled and none exist."""
    cfg = current_app.config
    if not cfg.get('TENANT_AUTO_CREATE', False):
        return None
    existing = Tenant.query.count()
    if existing > 0:
        return Tenant.query.filter_by(status='active').first()
    slug = cfg.get('TENANT_DEFAULT_SLUG', 'default')
    name = slug.replace('-', ' ').title()
    contact_email = cfg.get('DEFAULT_ADMIN_EMAIL') or 'admin@localhost'
    tenant = Tenant(
        slug=slug,
        name=name,
        contact_email=contact_email,
        status='active',
    )
    from app.extensions import db
    db.session.add(tenant)
    db.session.flush()
    return tenant


def resolve_tenant() -> Tenant | None:
    """Resolve current tenant from request context.

    Resolution order (first match wins):
      1. WSGI environ 'tenant.slug' (set by TenantPathWSGIMiddleware for /t/<slug>/ paths)
      2. Subdomain: <slug>.TENANT_BASE_DOMAIN
      3. Dedicated domain: Host header exactly matches tenant.domain
      4. Fallback: auto-create / first-active default when permitted
    """
    cfg = current_app.config
    saas = cfg.get('ENABLE_SAAS_MODE', False)

    # 1. Path-based: /t/<slug>/ (handled by WSGI middleware)
    slug = request.environ.get('tenant.slug')
    if slug:
        tenant = _get_tenant_by_slug(slug)
        if tenant:
            return tenant
        if not saas:
            return None
        raise TenantResolutionError(f"Unknown or inactive tenant slug: {slug}")

    # Non-SaaS mode: only path-based resolution applies
    if not saas:
        return None

    modes = {
        item.strip().lower()
        for item in str(cfg.get('TENANT_RESOLUTION_MODE', 'path')).split(',')
        if item.strip()
    }
    if 'all' in modes:
        modes = {'path', 'subdomain', 'domain'}

    host = (request.headers.get('Host', '') or '').split(':', 1)[0].lower()

    # 2. Subdomain: tenant.example.com
    base_domain = cfg.get('TENANT_BASE_DOMAIN')
    if 'subdomain' in modes and base_domain and host.endswith(f'.{base_domain}'):
        slug = host.replace(f'.{base_domain}', '')
        tenant = Tenant.query.filter_by(subdomain=slug, status='active').first()
        if tenant:
            return tenant

    # 3. Dedicated domain
    if 'domain' in modes and host:
        tenant = Tenant.query.filter_by(domain=host, status='active').first()
        if tenant:
            return tenant

    # 4. Fallback for SaaS: auto-create default or return first active
    tenant = _auto_create_default_tenant()
    if tenant:
        return tenant

    raise TenantResolutionError("No tenant could be resolved for this request.")

def set_tenant_context():
    """Flask before_request handler — injects full tenant context into g.

    In non-SaaS mode:
      - Path-based resolution (/t/<slug>/...) still works.
      - Without a tenant slug, all context values are None/empty.
    In SaaS mode:
      - Tenant MUST be resolved (raises 403 otherwise).
      - Module guards will later enforce module-level access.
    Exceptions: owner/super_admin API routes, auth routes bypass tenant requirement.
    """
    cfg = current_app.config
    saas = cfg.get('ENABLE_SAAS_MODE', False)

    # Paths that don't require tenant context
    # Owner routes (/owner/...) are exempt so super_admin can manage the platform
    # Super-admin routes (/super-admin/...) are exempt for cross-tenant administration
    # Auth routes (/auth/...) are exempt so users can login without tenant context
    # Static assets are exempt
    exempt_paths = [
        '/auth/',
        '/static/',
        '/favicon.ico',
        '/robots.txt',
        '/owner/',
        '/super-admin/',
    ]
    
    is_exempt = any(request.path.startswith(p) for p in exempt_paths)
    
    if is_exempt:
        tenant = None
    else:
        try:
            tenant = resolve_tenant()
        except TenantResolutionError as exc:
            if saas:
                from flask import abort
                abort(403, description=str(exc))
            tenant = None

    g.current_tenant = tenant
    g.tenant_id = tenant.id if tenant else None
    g.tenant_slug = tenant.slug if tenant else None
    g.enabled_modules = set()
    g.product_profile = None
    g.feature_flags = {}

    if tenant:
        try:
            from app.extensions import db
            from sqlalchemy import text
            db.session.execute(text(f"SET LOCAL app.tenant_id = '{tenant.id}'"))
        except Exception:
            pass

    if not tenant:
        return

    # Inject module/feature/profile context
    try:
        from app.core.module.validators import get_active_modules_for_tenant
        g.enabled_modules = get_active_modules_for_tenant(tenant.id)
    except Exception:
        g.enabled_modules = set() if saas else g.enabled_modules

    g.product_profile = tenant.product_profile_code

    try:
        from app.core.tenant.models import TenantFeatureFlag
        flags = TenantFeatureFlag.query.filter_by(
            tenant_id=tenant.id, is_enabled=True
        ).all()
        g.feature_flags = {f.feature_key: True for f in flags}
    except Exception:
        g.feature_flags = {}
