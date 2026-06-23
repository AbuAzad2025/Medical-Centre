"""Tenant/platform UI branding — single source for template ``ui.*`` vars."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional

from flask import g, url_for

DEFAULT_PRIMARY = '#0f4c81'
DEFAULT_SECONDARY = '#10b981'
DEFAULT_ACCENT = '#00a6a6'
DEFAULT_ORG_AR = 'المركز الصحي المتخصص'

_DEVELOPER_DEFAULTS = {
    'developer_company': 'شركة آزاد للأنظمة الذكية',
    'developer_name': 'المهندس أحمد غنام',
    'developer_mobile': '+ --------',
    'developer_location': 'رام الله - فلسطين',
}


@dataclass
class UIContext:
    organization_name: str
    organization_name_en: str
    logo_url: str
    primary_color: str
    secondary_color: str
    accent_color: str
    favicon_url: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _default_logo_url() -> str:
    return url_for('static', filename='img/azad_logo.png')


def _media_url(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    if path.startswith(('http://', 'https://', '/')):
        return path
    return url_for('static', filename=path.lstrip('/'))


def get_branding_row():
    """Active ``BrandingSettings`` row scoped to current tenant when possible."""
    try:
        from models.branding import BrandingSettings

        tenant = getattr(g, 'current_tenant', None)
        if tenant and getattr(tenant, 'id', None):
            row = BrandingSettings.query.filter_by(
                tenant_id=tenant.id, is_active=True
            ).first()
            if row:
                return row
        return BrandingSettings.get_active_settings()
    except Exception:
        return None


def _resolve_logo_url(tenant, branding_row) -> str:
    if tenant and getattr(tenant, 'logo_url', None):
        return tenant.logo_url
    if branding_row:
        url = _media_url(getattr(branding_row, 'logo_path', None))
        if url:
            return url
    return _default_logo_url()


def resolve_branding_context() -> UIContext:
    tenant = getattr(g, 'current_tenant', None)
    branding_row = get_branding_row()

    org = DEFAULT_ORG_AR
    org_en = ''
    if tenant and getattr(tenant, 'name', None):
        org = tenant.name
    elif branding_row and branding_row.organization_name:
        org = branding_row.organization_name
    if branding_row and branding_row.organization_name_en:
        org_en = branding_row.organization_name_en

    primary = DEFAULT_PRIMARY
    if tenant and getattr(tenant, 'primary_color', None):
        primary = tenant.primary_color
    elif branding_row and branding_row.primary_color:
        primary = branding_row.primary_color

    secondary = DEFAULT_SECONDARY
    accent = DEFAULT_ACCENT
    if branding_row:
        if branding_row.secondary_color:
            secondary = branding_row.secondary_color
        if branding_row.accent_color:
            accent = branding_row.accent_color

    favicon = _default_logo_url()
    if branding_row:
        fav = _media_url(branding_row.favicon_path)
        if fav:
            favicon = fav

    return UIContext(
        organization_name=org,
        organization_name_en=org_en,
        logo_url=_resolve_logo_url(tenant, branding_row),
        primary_color=primary,
        secondary_color=secondary,
        accent_color=accent,
        favicon_url=favicon,
    )


def resolve_ui_context() -> dict[str, str]:
    return resolve_branding_context().to_dict()


def load_developer_defaults(db, engine) -> dict[str, Optional[str]]:
    """Platform developer footer fields from ``SystemConfig``."""
    from sqlalchemy import inspect as sa_inspect
    from models.system_config import SystemConfig

    out = dict(_DEVELOPER_DEFAULTS)
    dev_logo = None
    try:
        if sa_inspect(engine).has_table('system_configs'):
            keys = {
                'developer_company': 'developer_company',
                'developer_name': 'developer_name',
                'developer_mobile': 'developer_mobile',
                'developer_location': 'developer_location',
            }
            for out_key, cfg_key in keys.items():
                row = SystemConfig.query.filter_by(config_key=cfg_key).first()
                if row:
                    val = row.get_value()
                    if val:
                        out[out_key] = val
            dl = SystemConfig.query.filter_by(config_key='developer_logo_url').first()
            if dl:
                dev_logo = dl.get_value()
    except Exception:
        pass
    out['developer_logo_url'] = dev_logo
    return out


def build_branding_payload(db, engine) -> dict[str, Any]:
    """Full context-processor payload (branding + ui + developer_*)."""
    branding_row = get_branding_row()
    ui = resolve_ui_context()
    dev = load_developer_defaults(db, engine)
    return {
        'branding': branding_row,
        'ui': ui,
        **dev,
    }
