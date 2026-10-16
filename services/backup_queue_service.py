"""Queue backup jobs via Celery."""

from __future__ import annotations

import os

from celery_app import celery_is_enabled, task_always_eager


class BackupQueueError(RuntimeError):
    """Raised when a backup cannot be queued."""


def queue_system_backup(backup_id: int, tenant_id: int | None = None) -> str:
    """Enqueue pg_dump execution; returns Celery task id.

    *tenant_id* is passed through to the task so it can bind that tenant before
    reading the row. This is not an optimisation: ``backups`` is RLS-protected
    by ``tenant_id = app.tenant_id``, so a worker that tries to discover the
    owning tenant *by reading the row first* cannot see the row at all. Every
    caller already holds the Backup object and therefore the tenant id.
    """
    if not celery_is_enabled() and not task_always_eager():
        raise BackupQueueError('celery_not_configured')

    from tasks.system_tasks import run_system_backup

    kwargs = {'tenant_id': tenant_id} if tenant_id is not None else {}

    if task_always_eager():
        # No bare `except Exception` here. Eager mode runs the task inline, and
        # swallowing its failure returned a truthy "eager-<id>" - so a backup
        # that never ran was indistinguishable from one that was queued. The
        # row stayed IN_PROGRESS forever with no error anywhere.
        result = run_system_backup.apply(args=[backup_id], kwargs=kwargs)
        return result.id or f'eager-{backup_id}'

    async_result = run_system_backup.delay(backup_id, **kwargs)
    if async_result.id is None:
        raise BackupQueueError('celery_task_id_missing')
    return async_result.id


def backup_queue_available() -> bool:
    return celery_is_enabled() or task_always_eager() or os.environ.get('FLASK_ENV') == 'testing'
