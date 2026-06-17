"""
Super Admin Service - Business logic for system administration.
Extracted from routes/super_admin/.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app_factory import db
from sqlalchemy import func


class SuperAdminService:
    """Centralized super admin business logic"""

    @staticmethod
    def get_system_stats() -> dict:
        from models.user import User
        from models.patient import Patient
        from models.visit import Visit
        from models.department import Department
        try:
            return {
                "users": User.query.count(),
                "patients": Patient.query.count(),
                "visits": Visit.query.count(),
                "departments": Department.query.count(),
                "active_users": User.query.filter(User.is_active == True).count(),
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
                username=data.get("username"),
                email=data.get("email"),
                role=data.get("role"),
                is_active=True,
                created_at=datetime.now(timezone.utc),
            )
            db.session.add(user)
            db.session.commit()
            return user
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error creating user: {str(e)}")
            return None

    @staticmethod
    def toggle_user_status(user_id: int) -> bool:
        from models.user import User
        user = User.query.get(user_id)
        if not user:
            return False
        user.is_active = not user.is_active
        db.session.commit()
        return True

    @staticmethod
    def get_security_logs(limit: int = 100) -> list:
        from models.audit_trail import AuditTrail
        return AuditTrail.query.order_by(AuditTrail.created_at.desc()).limit(limit).all()

    @staticmethod
    def get_system_config() -> dict:
        from models.system_config import SystemConfig
        configs = SystemConfig.query.all()
        return {c.key: c.value for c in configs}

    @staticmethod
    def update_system_config(key: str, value: str) -> bool:
        from models.system_config import SystemConfig
        try:
            config = SystemConfig.query.filter_by(key=key).first()
            if config:
                config.value = value
            else:
                config = SystemConfig(key=key, value=value)
                db.session.add(config)
            db.session.commit()
            return True
        except Exception:
            db.session.rollback()
            return False

    @staticmethod
    def get_database_stats() -> dict:
        try:
            from models.patient import Patient
            from models.user import User
            from models.visit import Visit
            from models.invoice import Invoice
            return {
                "patients": Patient.query.count(),
                "users": User.query.count(),
                "visits": Visit.query.count(),
                "invoices": Invoice.query.count(),
            }
        except Exception:
            return {}

    @staticmethod
    def get_audit_trail(user_id: int | None = None, action: str | None = None, limit: int = 200) -> list:
        from models.audit_trail import AuditTrail
        q = AuditTrail.query
        if user_id:
            q = q.filter_by(user_id=user_id)
        if action:
            q = q.filter(AuditTrail.action.ilike(f"%{action}%"))
        return q.order_by(AuditTrail.created_at.desc()).limit(limit).all()


# Singleton
super_admin_service = SuperAdminService()
