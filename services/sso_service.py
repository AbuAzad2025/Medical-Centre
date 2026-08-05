"""
SSO Service - SSO/LDAP configuration management.
Extracted from routes/sso_routes.py.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from app.extensions import db
from utils.db_safety import safe_commit
from utils.tenant_query import TenantContextError, get_tenant_record


class SSOService:
    """Centralized SSO/LDAP business logic"""

    @staticmethod
    def get_configs() -> list:
        from models import SSOConfiguration

        return db.session.execute(select(SSOConfiguration)).scalars().all()

    @staticmethod
    def get_active_configs() -> list:
        from models import SSOConfiguration

        return (
            db.session.execute(select(SSOConfiguration).filter_by(is_active=True)).scalars().all()
        )

    @staticmethod
    def get_config(config_id: int) -> Any | None:
        from models import SSOConfiguration

        return get_tenant_record(SSOConfiguration, config_id)

    @staticmethod
    def create_config(
        name: str,
        provider_type: str = 'ldap',
        server_url: str = '',
        base_dn: str = '',
        bind_dn: str = '',
        bind_password: str = '',
        auto_create_user: bool = False,
        default_role: str = 'user',
    ) -> Any | None:
        from models import SSOConfiguration

        try:
            cfg = SSOConfiguration(
                name=name,
                provider_type=provider_type,
                server_url=server_url,
                base_dn=base_dn,
                bind_dn=bind_dn,
                bind_password=bind_password,
                auto_create_user=auto_create_user,
                default_role=default_role,
            )
            db.session.add(cfg)
            if not safe_commit(db.session, error_message='Failed to create SSO config'):
                return None
            return cfg
        except Exception:
            logging.exception("Error creating SSO config: %s")
            return None

    @staticmethod
    def toggle_config(config_id: int) -> bool:
        from models import SSOConfiguration

        try:
            cfg = get_tenant_record(SSOConfiguration, config_id)
        except TenantContextError:
            return False
        cfg.is_active = not cfg.is_active
        safe_commit(db.session, error_message='Failed to toggle SSO config', reraise=True)
        return True

    @staticmethod
    def delete_config(config_id: int) -> bool:
        from models import SSOConfiguration

        try:
            cfg = get_tenant_record(SSOConfiguration, config_id)
        except TenantContextError:
            return False
        db.session.delete(cfg)
        safe_commit(db.session, error_message='Failed to delete SSO config', reraise=True)
        return True


# Singleton
sso_service = SSOService()
