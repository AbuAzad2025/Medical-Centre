"""
Flask Extensions — centralized to avoid circular imports
ALL instances come from app_factory so Alembic sees the same metadata.
"""
from app_factory import db, login_manager, migrate, mail, csrf, socketio

__all__ = ["db", "login_manager", "migrate", "mail", "csrf", "socketio"]

