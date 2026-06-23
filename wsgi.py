"""WSGI entrypoint for gunicorn and Flask CLI (migrations)."""
from app_factory import create_app

app = create_app()
