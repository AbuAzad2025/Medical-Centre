"""Infrastructure Celery tasks."""
from __future__ import annotations

import logging

from celery_app import get_celery_app
from services.backup_automation_service import BackupAutomationError

logger = logging.getLogger(__name__)

celery = get_celery_app()


@celery.task(name='tasks.run_system_backup', bind=True)
def run_system_backup(self, backup_id: int) -> dict:
    """Run pg_dump for a queued Backup record outside the web request cycle."""
    from services.backup_execution_service import execute_backup_by_id

    try:
        record = execute_backup_by_id(backup_id)
        return {
            'backup_id': backup_id,
            'status': record.backup_status,
            'size': record.backup_size,
            'task_id': self.request.id,
        }
    except BackupAutomationError as exc:
        logger.error('Celery backup task failed backup_id=%s: %s', backup_id, exc)
        raise
