"""
Medical Centre Platform — Modular Application Package
All application setup is handled by app_factory.py.
This package exists for model imports only.
"""

from app.extensions import csrf, db, login_manager, mail, migrate, socketio
