"""Infrastructure Celery tasks."""
from __future__ import annotations

import logging

from celery_app import get_celery_app
from services.backup_automation_service import BackupAutomationError

logger = logging.getLogger(__name__)

celery = get_celery_app()


def _load_backup_without_tenant_context(backup_id: int):
    """Load a Backup row bypassing ORM tenant filters (Celery has no request tenant)."""
    from flask import g

    from app.extensions import db
    from models.backup import Backup

    prev = g.get('_tenant_filter_bypass', False)
    g._tenant_filter_bypass = True
    try:
        return db.session.get(Backup, backup_id)
    finally:
        if prev:
            g._tenant_filter_bypass = True
        else:
            g.pop('_tenant_filter_bypass', None)


@celery.task(name='tasks.run_system_backup', bind=True)
def run_system_backup(self, backup_id: int) -> dict:
    """Run pg_dump for a queued Backup record outside the web request cycle."""
    from flask import current_app

    from services.backup_execution_service import execute_backup_by_id
    from services.tenant_job_runner import get_flask_app, with_tenant_context

    app = get_flask_app() or current_app._get_current_object()
    backup = _load_backup_without_tenant_context(backup_id)
    if backup is None:
        raise BackupAutomationError(f'Backup record {backup_id} not found')

    try:
        if backup.tenant_id is not None:
            outcome = with_tenant_context(
                app,
                backup.tenant_id,
                lambda: _backup_result_tuple(execute_backup_by_id, backup_id),
            )
        else:
            outcome = _backup_result_tuple(execute_backup_by_id, backup_id)
    except BackupAutomationError as exc:
        logger.error('Celery backup task failed backup_id=%s: %s', backup_id, exc)
        raise

    if outcome is None:
        raise BackupAutomationError(f'Backup tenant {backup.tenant_id} not found for backup {backup_id}')

    status, size = outcome
    return {
        'backup_id': backup_id,
        'status': status,
        'size': size,
        'task_id': self.request.id,
    }


def _backup_result_tuple(execute_fn, backup_id: int):
    record = execute_fn(backup_id)
    return record.backup_status, record.backup_size
