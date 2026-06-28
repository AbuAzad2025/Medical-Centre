"""Queue backup jobs via Celery."""
from __future__ import annotations

import os
from typing import Optional

from celery_app import celery_is_enabled, get_celery_app, task_always_eager


class BackupQueueError(RuntimeError):
    """Raised when a backup cannot be queued."""


def queue_system_backup(backup_id: int) -> str:
    """Enqueue pg_dump execution; returns Celery task id."""
    if not celery_is_enabled() and not task_always_eager():
        raise BackupQueueError('celery_not_configured')

    from tasks.system_tasks import run_system_backup

    if task_always_eager():
        result = run_system_backup.apply(args=[backup_id])
        return result.id or f'eager-{backup_id}'

    async_result = run_system_backup.delay(backup_id)
    if async_result.id is None:
        raise BackupQueueError('celery_task_id_missing')
    return async_result.id


def backup_queue_available() -> bool:
    return celery_is_enabled() or task_always_eager() or os.environ.get('FLASK_ENV') == 'testing'
