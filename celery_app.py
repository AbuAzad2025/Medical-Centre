"""Celery application factory for background infrastructure tasks."""

from __future__ import annotations

import os
from datetime import timedelta
from typing import Optional

from celery import Celery

_celery: Optional[Celery] = None


def broker_url() -> str:
    return (
        os.environ.get('CELERY_BROKER_URL', '').strip()
        or os.environ.get('REDIS_URL', '').strip()
        or 'redis://localhost:6379/0'
    )


def celery_is_enabled() -> bool:
    return os.environ.get('CELERY_ENABLED', 'false').lower() in ('true', '1', 'on')


def task_always_eager() -> bool:
    return os.environ.get('CELERY_TASK_ALWAYS_EAGER', '').lower() in ('true', '1', 'on')


def get_celery_app() -> Celery:
    global _celery
    if _celery is None:
        _celery = Celery(
            'medical_system',
            broker=broker_url(),
            backend=broker_url(),
            include=['tasks.system_tasks'],
        )
        _celery.conf.update(
            task_serializer='json',
            accept_content=['json'],
            result_serializer='json',
            timezone='UTC',
            enable_utc=True,
            task_always_eager=task_always_eager(),
            task_eager_propagates=True,
            task_track_started=True,
            beat_schedule={
                # Daily at 2:00 AM UTC - purge expired tokens
                'purge-expired-tokens-daily': {
                    'task': 'tasks.purge_expired_tokens',
                    'schedule': timedelta(days=1),
                    'options': {'queue': 'maintenance'},
                },
                # Weekly on Sunday at 3:00 AM UTC - purge old audit logs
                'purge-old-audit-logs-weekly': {
                    'task': 'tasks.purge_old_audit_logs',
                    'schedule': timedelta(weeks=1),
                    'options': {'queue': 'maintenance'},
                },
                # Daily at 4:00 AM UTC - purge stale notifications
                'purge-stale-notifications-daily': {
                    'task': 'tasks.purge_stale_notifications',
                    'schedule': timedelta(days=1),
                    'options': {'queue': 'maintenance'},
                },
                # Daily at 5:00 AM UTC - run all maintenance
                'run-all-maintenance-daily': {
                    'task': 'tasks.run_all_maintenance',
                    'schedule': timedelta(days=1),
                    'options': {'queue': 'maintenance'},
                },
            },
        )
    return _celery


def init_celery_app(flask_app) -> Celery:
    """Bind Celery tasks to the Flask application context."""
    from services.tenant_job_runner import bind_flask_app

    celery = get_celery_app()
    celery.flask_app = flask_app
    bind_flask_app(flask_app)

    class FlaskContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with flask_app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = FlaskContextTask
    return celery
