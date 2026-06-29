"""Celery worker entrypoint with Flask app context."""
from app_factory import create_app
from celery_app import get_celery_app, init_celery_app

app = create_app()
celery = init_celery_app(app)
