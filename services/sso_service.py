"""
SSO Service - SSO/LDAP configuration management.
Extracted from routes/sso_routes.py.
"""
from __future__ import annotations

import logging
from typing import Any

from app_factory import db


class SSOService:
    """Centralized SSO/LDAP business logic"""

    @staticmethod
    def get_configs() -> list:
        from models import SSOConfiguration
        return SSOConfiguration.query.all()

    @staticmethod
    def get_active_configs() -> list:
        from models import SSOConfiguration
        return SSOConfiguration.query.filter_by(is_active=True).all()

    @staticmethod
    def get_config(config_id: int) -> Any | None:
        from models import SSOConfiguration
        return SSOConfiguration.query.get(config_id)

    @staticmethod
    def create_config(name: str, provider_type: str = "ldap",
                      server_url: str = "", base_dn: str = "",
                      bind_dn: str = "", bind_password: str = "",
                      auto_create_user: bool = False,
                      default_role: str = "user") -> Any | None:
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
            db.session.commit()
            return cfg
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating SSO config: {str(e)}")
            return None

    @staticmethod
    def toggle_config(config_id: int) -> bool:
        from models import SSOConfiguration
        cfg = SSOConfiguration.query.get(config_id)
        if not cfg:
            return False
        cfg.is_active = not cfg.is_active
        db.session.commit()
        return True

    @staticmethod
    def delete_config(config_id: int) -> bool:
        from models import SSOConfiguration
        cfg = SSOConfiguration.query.get(config_id)
        if not cfg:
            return False
        db.session.delete(cfg)
        db.session.commit()
        return True


# Singleton
sso_service = SSOService()
