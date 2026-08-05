"""
Medical Centre Platform — Modular Application Package
All application setup is handled by app_factory.py.
This package exists for model imports only.
"""

from app.extensions import csrf as csrf
from app.extensions import db as db
from app.extensions import login_manager as login_manager
from app.extensions import mail as mail
from app.extensions import migrate as migrate
from app.extensions import socketio as socketio
