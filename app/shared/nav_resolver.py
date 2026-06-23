"""Dynamic navigation — MODULE_REGISTRY + tenant modules + role scope."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Set

from flask import g

from app.core.module.registry import MODULE_REGISTRY, ModuleMeta

# Registry key aliases from ModulePermission.module_name
_MODULE_ALIASES = {
    'accounting': 'billing',
    'admin': 'reporting',
    'dicom': 'radiology',
}

# Fallback when ModulePermission rows are missing (standalone / legacy DB)
_ROLE_MODULE_FALLBACK: dict[str, Optional[Set[str]]] = {
    'super_admin': None,
    'admin': None,
    'manager': {'reporting', 'billing', 'appointments', 'inventory', 'reception'},
    'reception': {'reception', 'appointments', 'billing'},
    'doctor': {'doctor'},
    'lab': {'lab'},
    'radiology': {'radiology', 'ai_imaging'},
    'pharmacist': {'pharmacy', 'inventory'},
    'pharmacy': {'pharmacy', 'inventory'},
    'emergency': {'emergency'},
    'nurse': {'nursing'},
    'accountant': {'billing'},
    'patient': {'portal'},
    'owner': set(),
}


@dataclass(frozen=True)
class NavItem:
    id: str
    label_ar: str
    icon: str
    href: str
    active_prefix: str = ''
    module: Optional[str] = None
    permission: Optional[str] = None


@dataclass
class NavSection:
    id: str
    title_ar: str
    items: List[NavItem] = field(default_factory=list)


def _normalize_module(name: str) -> str:
    return _MODULE_ALIASES.get(name, name)


def _enabled_modules_for_nav() -> Set[str]:
    enabled = set(getattr(g, 'enabled_modules', None) or [])
    if enabled:
        return enabled
    tenant = getattr(g, 'current_tenant', None)
    if tenant and getattr(tenant, 'id', None):
        try:
            from app.core.module.validators import get_active_modules_for_tenant
            return set(get_active_modules_for_tenant(tenant.id))
        except Exception:
            pass
    return set(MODULE_REGISTRY.keys())


def _user_allowed_modules(user, enabled: Set[str]) -> Set[str]:
    role = getattr(user, 'role', None) or ''
    if role in ('super_admin', 'admin'):
        return {m for m in enabled if m != 'owner'}

    tenant = getattr(g, 'current_tenant', None)
    tenant_id = tenant.id if tenant else getattr(user, 'tenant_id', None)

    try:
        from services.permission_scope_service import PermissionScopeService
        scoped = PermissionScopeService.get_accessible_module_names(user.id, tenant_id)
        if scoped:
            normalized = {_normalize_module(m) for m in scoped}
            return {m for m in normalized if m in enabled and m != 'owner'}
    except Exception:
        pass

    fallback = _ROLE_MODULE_FALLBACK.get(role)
    if fallback is None:
        if role in MODULE_REGISTRY and role in enabled:
            return {role}
        return {m for m in enabled if m != 'owner'}
    return {m for m in fallback if m in enabled}


def _active_prefix(meta: ModuleMeta) -> str:
    if meta.route_prefixes:
        return meta.route_prefixes[0]
    route = (meta.default_route or '').strip()
    if route.startswith('/'):
        parts = [p for p in route.split('/') if p]
        return f'/{parts[0]}' if parts else '/'
    return ''


def _tenant_path(path: str) -> str:
    """Prefix staff paths with /t/<slug>/ in SaaS mode (matches tenant_url_for rules)."""
    from flask import current_app
    if not path.startswith('/'):
        return path
    if path.startswith(('/owner/', '/super-admin/', '/auth/', '/static/')):
        return path
    if not current_app.config.get('ENABLE_SAAS_MODE', False):
        return path
    slug = getattr(g, 'tenant_slug', None)
    if not slug:
        return path
    return f'/t/{slug}{path}'


def _module_path(meta: ModuleMeta) -> str:
    route = meta.default_route or '#'
    if route.startswith('/'):
        return route
    return f'/{route}'


def _module_href(meta: ModuleMeta) -> str:
    return _tenant_path(_module_path(meta))


def resolve_nav_for_user(user) -> List[NavSection]:
    if not user or not getattr(user, 'is_authenticated', False):
        return []

    enabled = _enabled_modules_for_nav()
    allowed = _user_allowed_modules(user, enabled)
    role = getattr(user, 'role', None) or ''

    sections: List[NavSection] = []

    main = NavSection(id='main', title_ar='')
    main.items.append(NavItem(
        id='home',
        label_ar='الرئيسية',
        icon='fas fa-home',
        href='/',
        active_prefix='__home__',
    ))
    sections.append(main)

    modules = NavSection(id='modules', title_ar='الوحدات')
    for module_name, meta in MODULE_REGISTRY.items():
        if module_name == 'owner':
            continue
        if module_name not in allowed:
            continue
        if module_name not in enabled:
            continue
        modules.items.append(NavItem(
            id=module_name,
            label_ar=meta.name_ar,
            icon=meta.icon or 'fas fa-circle',
            href=_module_href(meta),
            active_prefix=_active_prefix(meta),
            module=module_name,
        ))
    if modules.items:
        sections.append(modules)

    # G-03: super_admin/admin ≠ platform owner role
    if role in ('super_admin', 'admin'):
        admin = NavSection(id='admin', title_ar='الإدارة')
        admin.items.append(NavItem(
            id='super_admin',
            label_ar='إعدادات المركز',
            icon='fas fa-cogs',
            href=_tenant_path('/super-admin/dashboard'),
            active_prefix='/super-admin',
        ))
        sections.append(admin)
    elif role == 'owner':
        platform = NavSection(id='platform', title_ar='المنصة')
        platform.items.append(NavItem(
            id='owner_dashboard',
            label_ar='لوحة المالك',
            icon='fas fa-crown',
            href=_tenant_path('/owner/dashboard'),
            active_prefix='/owner',
        ))
        sections.append(platform)

    return sections
