"""
Tenant Resolution Middleware
Resolves tenant from subdomain, path (/t/<slug>/), or dedicated domain.
Provides TenantPathWSGIMiddleware to rewrite /t/<slug>/... → /...
and set_tenant_context() as the Flask before_request handler.
"""
from flask import current_app, request, g
from sqlalchemy import select, func, text
from app.extensions import db
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
    """Return login-eligible tenant by slug (active, trial, or pending payment)."""
    from app.shared.enums import TenantStatus

    return db.session.execute(select(Tenant).filter(
        Tenant.slug == slug,
        Tenant.status.in_((TenantStatus.ACTIVE, TenantStatus.TRIAL, TenantStatus.PENDING)),
    )).scalars().first()


_PENDING_ALLOWED_PREFIXES = (
    '/auth/',
    '/api/billing/',
    '/saas/',
    '/static/',
    '/favicon.ico',
)


def _auto_create_default_tenant() -> Tenant | None:
    """Auto-create a default tenant if TENANT_AUTO_CREATE is enabled and none exist."""
    cfg = current_app.config
    if not cfg.get('TENANT_AUTO_CREATE', False):
        return None
    existing = db.session.execute(select(func.count()).select_from(Tenant)).scalar()
    if existing > 0:
        return db.session.execute(select(Tenant).filter_by(status='active')).scalars().first()
    slug = cfg.get('TENANT_DEFAULT_SLUG', 'default')
    name = slug.replace('-', ' ').title()
    contact_email = cfg.get('DEFAULT_ADMIN_EMAIL') or 'admin@localhost'
    tenant = Tenant(
        slug=slug,
        name=name,
        contact_email=contact_email,
        status='active',
    )
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
        tenant = db.session.execute(select(Tenant).filter_by(subdomain=slug, status='active')).scalars().first()
        if tenant:
            return tenant

    # 3. Dedicated domain
    if 'domain' in modes and host:
        tenant = db.session.execute(select(Tenant).filter_by(domain=host, status='active')).scalars().first()
        if tenant:
            return tenant

    # 4. Fallback for SaaS: auto-create default or return first active
    tenant = _auto_create_default_tenant()
    if tenant:
        return tenant

    raise TenantResolutionError("No tenant could be resolved for this request.")


def _tenant_from_authenticated_user() -> Tenant | None:
    """Resolve tenant from session or the logged-in user's ``tenant_id``."""
    try:
        from flask import g, session
        from models.user import User

        tid = session.get('tenant_id')
        if tid:
            return db.session.get(Tenant, int(tid))

        slug = session.get('tenant_slug')
        if slug:
            tenant = _get_tenant_by_slug(slug)
            if tenant:
                return tenant

        user_id = session.get('_user_id')
        if not user_id:
            try:
                from flask_login import current_user
                if current_user.is_authenticated:
                    user_id = current_user.id
                    tid = getattr(current_user, 'tenant_id', None)
                    if tid:
                        return db.session.get(Tenant, tid)
            except Exception:
                pass
        if not user_id:
            return None

        prev_bypass = g.get('_tenant_filter_bypass', False)
        g._tenant_filter_bypass = True
        try:
            user = db.session.get(User, int(user_id))
        finally:
            if prev_bypass:
                g._tenant_filter_bypass = True
            else:
                g.pop('_tenant_filter_bypass', None)

        if user and user.tenant_id:
            return db.session.get(Tenant, user.tenant_id)
    except Exception:
        return None
    return None


def bind_tenant_from_session() -> None:
    """Bind tenant from session keys before Flask-Login user_loader runs."""
    from flask import g, session

    if g.get('tenant_id'):
        return

    tid = session.get('tenant_id')
    if tid:
        tenant = db.session.get(Tenant, int(tid))
        if tenant:
            bind_g_tenant(tenant)
            return

    slug = session.get('tenant_slug')
    if slug:
        tenant = _get_tenant_by_slug(slug)
        if tenant:
            bind_g_tenant(tenant)


def bind_g_tenant(tenant: Tenant | None) -> None:
    """Set ``g.tenant_id`` and PostgreSQL RLS session var for a resolved tenant."""
    g.current_tenant = tenant
    g.tenant_id = tenant.id if tenant else None
    g.tenant_slug = tenant.slug if tenant else None
    if not tenant:
        return
    try:
        from sqlalchemy import text, select, func
        db.session.execute(text(f"SET LOCAL app.tenant_id = '{tenant.id}'"))
        db.session.info['_tenant_id'] = tenant.id
    except Exception:
        pass


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
        '/api/saas/',
        '/saas/',
        '/api/billing/stripe/',
        '/__health',
        '/health',
        '/metrics',
        '/kiosk/',
        '/pwa/',
        '/privacy-policy',
        '/terms-of-use',
        '/technical-support',
        '/about-system',
        '/_ghost_whoami',
        '/medication/sales/',
        '/medication/print/',
    ]

    is_exempt = any(request.path.startswith(p) for p in exempt_paths) or request.path == '/'

    bind_tenant_from_session()
    tenant = g.get('current_tenant')

    if tenant is None and not is_exempt:
        try:
            tenant = resolve_tenant()
        except TenantResolutionError as exc:
            if saas and not g.get('tenant_id'):
                from flask import abort
                abort(403, description=str(exc))
            tenant = None

    if tenant is None:
        tenant = _tenant_from_authenticated_user()

    # Module guard paths - let module guards handle access control instead of aborting here
    MODULE_GUARD_PREFIXES = (
        '/lab/', '/radiology/', '/nurse/', '/reception/', '/medication/',
        '/finance/', '/accountant/', '/booking/', '/manager/', '/barcode/',
        '/patient-education/', '/telemedicine/', '/clinical-coding/',
        '/specialty-forms/', '/referral/', '/vaccination/', '/pathway/',
        '/cds/', '/emar/', '/bed/', '/or/', '/nursing-assessment/',
        '/backup/', '/backup-restore/', '/ai-imaging/', '/dicom/', '/fhir/',
        '/sso/', '/api/search/', '/api/user/', '/api/dashboard/',
        '/population-health/', '/data-warehouse/', '/report-builder/',
        '/quality/', '/what-if/', '/monitoring/', '/security/', '/mfa/',
        '/biometric/', '/custom-report/', '/kiosk/', '/doctor/', '/emergency/',
    )

    if saas and not is_exempt and tenant is None:
        # Check if this is a module guard path - if so, let the module guard handle access control
        is_module_guard_path = any(request.path.startswith(p) for p in MODULE_GUARD_PREFIXES)
        if is_module_guard_path:
            # Don't abort here - let the module guard handle access control
            pass
        else:
            try:
                from flask_login import current_user
                if not current_user.is_authenticated:
                    g.current_tenant = None
                    g.tenant_id = None
                    g.tenant_slug = None
                    g.enabled_modules = set()
                    g.product_profile = None
                    g.feature_flags = {}
                    return
            except Exception:
                pass
            from flask import abort
            abort(403, description='No tenant could be resolved for this request.')

    g.enabled_modules = set()
    g.product_profile = None
    g.feature_flags = {}

    if tenant:
        bind_g_tenant(tenant)

        # R4: Redirect bare tenant-scoped requests to /t/<slug>/ prefix
        # If the user has tenant context but accessed the resource without
        # the /t/<slug>/ path prefix (i.e., the WSGI middleware didn't
        # extract the slug), redirect them to the canonical URL.
        # Only redirect if user is authenticated (login_required will handle unauth).
        # IMPORTANT: Only redirect if the module is active for this tenant.
        # If the module is disabled, let the module guard return 403 instead of redirecting.
        # IMPORTANT: Check for cross-tenant access - if the request path has a different
        # tenant slug than the user's tenant, skip redirect and let cross-tenant check handle it.
        if (not request.environ.get('tenant.slug')
                and not is_exempt
                and request.method in ('GET', 'HEAD')):
            try:
                from flask_login import current_user
                if current_user.is_authenticated:
                    # Check if the request path has a different tenant slug (cross-tenant access)
                    # Skip R4 redirect for cross-tenant paths - let enforce_tenant_access handle it
                    path_parts = request.path.strip('/').split('/')
                    if len(path_parts) >= 2 and path_parts[0] == 't':
                        path_tenant_slug = path_parts[1]
                        if path_tenant_slug != (tenant.slug or ''):
                            # Cross-tenant path - skip R4 redirect, let enforce_tenant_access handle
                            pass
                        else:
                            # Same tenant - proceed with module check and redirect
                            # Check if the module for this path is active for this tenant
                            module_name = None
                            for prefix in MODULE_GUARD_PREFIXES:
                                if request.path.startswith(prefix):
                                    module_name = prefix.strip('/').split('/')[0]
                                    break
                            
                            if module_name:
                                try:
                                    from app.core.module.validators import get_active_modules_for_tenant
                                    active_modules = get_active_modules_for_tenant(tenant.id)
                                    if module_name not in active_modules:
                                        # Module is disabled - don't redirect, let module guard return 403
                                        pass
                                    else:
                                        from flask import redirect
                                        query = request.query_string.decode() if request.query_string else ''
                                        target = f'/t/{tenant.slug}{request.path}'
                                        if query:
                                            target += f'?{query}'
                                        return redirect(target)
                                except Exception:
                                    pass
                            else:
                                from flask import redirect
                                query = request.query_string.decode() if request.query_string else ''
                                target = f'/t/{tenant.slug}{request.path}'
                                if query:
                                    target += f'?{query}'
                                return redirect(target)
            except Exception:
                pass
    else:
        g.current_tenant = None
        g.tenant_id = None
        g.tenant_slug = None

    if not tenant:
        return

    # DEBUG
    import logging
    logging.getLogger(__name__).info(f"set_tenant_context: path={request.path}, is_exempt={is_exempt}, tenant_id={getattr(tenant, 'id', None)}, enabled_modules={getattr(g, 'enabled_modules', None)}")

    # MC-005: enforce tenant-access for authenticated users
    if not is_exempt:
        actor = getattr(g, "current_user", None)
        if actor is None:
            try:
                from flask_login import current_user

                if current_user.is_authenticated:
                    actor = current_user
            except Exception:
                actor = None
        actor_role = getattr(actor, "role", None) if actor else None
        # Only the Ghost Mode master (platform_owner) is exempt from pre-enforcement;
        # the ghost middleware re-resolves the impersonated context afterwards.
        # super_admin/owner cross-tenant access is still gated by
        # enforce_tenant_access() via the explicit assumption mechanism.
        if actor_role != "platform_owner":
            try:
                from app.core.tenant.assumption_service import PlatformAssumptionService

                PlatformAssumptionService.enforce_tenant_access()
            except Exception:
                from flask import abort

                abort(403, description="Cross-tenant access denied")

    from app.shared.enums import TenantStatus
    if tenant.status == TenantStatus.PENDING:
        if not any(request.path.startswith(p) for p in _PENDING_ALLOWED_PREFIXES):
            from flask import abort
            abort(402, description='Subscription payment required before accessing this resource.')

    # Inject module/feature/profile context
    try:
        from app.core.module.validators import get_active_modules_for_tenant

        g.enabled_modules = get_active_modules_for_tenant(tenant.id)
    except Exception:
        g.enabled_modules = set() if saas else g.enabled_modules

    g.product_profile = tenant.product_profile_code

    try:
        from app.core.tenant.models import TenantFeatureFlag

        flags = db.session.execute(select(TenantFeatureFlag).filter_by(
            tenant_id=tenant.id, is_enabled=True
        )).scalars().all()
        g.feature_flags = {f.feature_key: True for f in flags}
    except Exception:
        g.feature_flags = {}