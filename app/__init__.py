"""
Medical Centre Platform — Modular Application Package
All application setup is handled by app_factory.py.
This package exists for model imports only.
"""
from app.extensions import db, login_manager, migrate, mail, csrf, socketio
