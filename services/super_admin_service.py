"""
Super Admin Service - Business logic for system administration.
Extracted from routes/super_admin/.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select

from app.extensions import db
from utils.db_safety import safe_commit
from utils.tenant_query import TenantContextError, get_tenant_record


class SuperAdminService:
    """Centralized super admin business logic"""

    @staticmethod
    def get_system_stats() -> dict:
        from models.department import Department
        from models.patient import Patient
        from models.user import User
        from models.visit import Visit

        try:
            return {
                'users': db.session.execute(select(func.count()).select_from(User)).scalar(),
                'patients': db.session.execute(select(func.count()).select_from(Patient)).scalar(),
                'visits': db.session.execute(select(func.count()).select_from(Visit)).scalar(),
                'departments': db.session.execute(
                    select(func.count()).select_from(Department)
                ).scalar(),
                'active_users': db.session.execute(
                    select(func.count()).select_from(User).filter(User.is_active == True)
                ).scalar(),
            }
        except Exception:
            return {}

    @staticmethod
    def get_all_users(role: str | None = None, active: bool | None = None) -> list:
        from models.user import User

        q = User.query
        if role:
            q = q.filter_by(role=role)
        if active is not None:
            q = q.filter_by(is_active=active)
        return q.order_by(User.created_at.desc()).all()

    @staticmethod
    def create_user(data: dict) -> Any | None:
        from models.user import User

        try:
            user = User(
                username=data.get('username'),
                email=data.get('email'),
                role=data.get('role'),
                is_active=True,
                created_at=datetime.now(UTC),
            )
            db.session.add(user)
            if not safe_commit(db.session, error_message='Failed to create user'):
                return None
            return user
        except Exception as e:
            logging.exception(f'Error creating user: {e!s}')
            return None

    @staticmethod
    def toggle_user_status(user_id: int) -> bool:
        from models.user import User

        try:
            user = get_tenant_record(User, user_id)
        except TenantContextError:
            return False
        user.is_active = not user.is_active
        safe_commit(db.session, error_message='Failed to toggle user status', reraise=True)
        return True

    @staticmethod
    def get_security_logs(limit: int = 100) -> list:
        from models.audit_trail import AuditTrail

        return (
            db.session.execute(
                select(AuditTrail).order_by(AuditTrail.created_at.desc()).limit(limit)
            )
            .scalars()
            .all()
        )

    @staticmethod
    def get_system_config() -> dict:
        from models.system_config import SystemConfig

        configs = db.session.execute(select(SystemConfig)).scalars().all()
        return {c.key: c.value for c in configs}

    @staticmethod
    def update_system_config(key: str, value: str) -> bool:
        from models.system_config import SystemConfig

        try:
            config = db.session.execute(select(SystemConfig).filter_by(key=key)).scalars().first()
            if config:
                config.value = value
            else:
                config = SystemConfig(key=key, value=value)
                db.session.add(config)
            return safe_commit(db.session, error_message='Failed to update config')
        except Exception:
            return False

    @staticmethod
    def get_database_stats() -> dict:
        try:
            from models.invoice import Invoice
            from models.patient import Patient
            from models.user import User
            from models.visit import Visit

            return {
                'patients': db.session.execute(select(func.count()).select_from(Patient)).scalar(),
                'users': db.session.execute(select(func.count()).select_from(User)).scalar(),
                'visits': db.session.execute(select(func.count()).select_from(Visit)).scalar(),
                'invoices': db.session.execute(select(func.count()).select_from(Invoice)).scalar(),
            }
        except Exception:
            return {}

    @staticmethod
    def get_audit_trail(
        user_id: int | None = None, action: str | None = None, limit: int = 200
    ) -> list:
        from models.audit_trail import AuditTrail

        q = AuditTrail.query
        if user_id:
            q = q.filter_by(user_id=user_id)
        if action:
            q = q.filter(AuditTrail.action.ilike(f'%{action}%'))
        return q.order_by(AuditTrail.created_at.desc()).limit(limit).all()


# Singleton
super_admin_service = SuperAdminService()
