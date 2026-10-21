"""Queue backup jobs via Celery."""

from __future__ import annotations

import logging
import os

from celery_app import celery_is_enabled, task_always_eager
from services.backup_automation_service import BackupExecutionError

logger = logging.getLogger(__name__)


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
        # Eager mode runs the task inline, so its failure reaches the caller
        # directly. Swallowing every failure here returned a truthy
        # "eager-<id>" for a backup that never ran, and that was
        # indistinguishable from one that had been queued.
        #
        # But the failure is not always unrecorded. The execution service
        # writes FAILED and the error onto the row before it raises, so in that
        # case the outcome is on the row and the request was in fact accepted
        # - the work was dispatched and it failed on its own terms. Answering
        # 500 there hid the accepted request behind a failure the row already
        # records, and it made the endpoint's answer depend on whether the
        # machine running it happens to have pg_dump installed.
        #
        # So: a failure whose outcome reached the row is reported as accepted,
        # and a failure that left the row without an outcome is raised.
        try:
            result = run_system_backup.apply(args=[backup_id], kwargs=kwargs)
        except BackupExecutionError as exc:
            # The row carries the outcome, so the request was accepted and the
            # work failed on its own terms. Answering 500 here would hide an
            # accepted request behind a failure the row already records, and
            # it made the endpoint's answer depend on whether the machine
            # running it happens to have pg_dump installed.
            logger.warning('Backup %s failed while running eagerly: %s', backup_id, exc)
            return f'eager-{backup_id}'
        return result.id or f'eager-{backup_id}'

    async_result = run_system_backup.delay(backup_id, **kwargs)
    if async_result.id is None:
        raise BackupQueueError('celery_task_id_missing')
    return async_result.id


def backup_queue_available() -> bool:
    return celery_is_enabled() or task_always_eager() or os.environ.get('FLASK_ENV') == 'testing'
