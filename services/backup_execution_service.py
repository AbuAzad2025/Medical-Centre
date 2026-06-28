"""Execute PostgreSQL backups (used by web routes and Celery workers)."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from app.extensions import db
from app.shared.enums import BackupStatus
from models.backup import Backup
from services.backup_automation_service import BackupAutomationError, BackupAutomationService
from services.pg_backup_service import PgBackupError, run_pg_dump_sql_gz

logger = logging.getLogger(__name__)


def execute_backup_by_id(backup_id: int) -> Backup:
    """Run pg_dump for an existing Backup record and update its status."""
    backup = db.session.get(Backup, backup_id)
    if backup is None:
        raise BackupAutomationError(f'Backup record {backup_id} not found')

    backup.backup_status = BackupStatus.IN_PROGRESS
    backup.started_at = backup.started_at or datetime.now(timezone.utc)
    db.session.commit()

    try:
        size = run_pg_dump_sql_gz(backup.backup_path)
        backup.backup_size = size
        backup.backup_status = BackupStatus.COMPLETED
        backup.completed_at = datetime.now(timezone.utc)
        cloud_uri = BackupAutomationService.upload_to_cloud(backup.backup_path)
        if cloud_uri:
            backup.backup_notes = f'cloud_uri={cloud_uri}'
        db.session.commit()
        logger.info('Backup completed id=%s path=%s', backup.id, backup.backup_path)
        return backup
    except PgBackupError as exc:
        backup.backup_status = BackupStatus.FAILED
        backup.backup_notes = str(exc)
        if os.path.exists(backup.backup_path):
            try:
                os.remove(backup.backup_path)
            except OSError:
                pass
        db.session.commit()
        logger.error('Backup failed id=%s: %s', backup.id, exc)
        raise BackupAutomationError(str(exc)) from exc
