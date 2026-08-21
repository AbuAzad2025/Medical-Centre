"""
Flask Extensions — centralized to avoid circular imports
ALL instances come from app_factory so Alembic sees the same metadata.
"""

from app_factory import csrf, db, login_manager, mail, migrate, sess, socketio

__all__ = ['csrf', 'db', 'login_manager', 'mail', 'migrate', 'sess', 'socketio']
