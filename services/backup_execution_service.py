"""Execute PostgreSQL backups (used by web routes and Celery workers)."""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime

from app.extensions import db
from app.shared.enums import BackupStatus
from models.backup import Backup
from services.backup_automation_service import BackupAutomationError, BackupAutomationService
from services.pg_backup_service import PgBackupError, run_pg_dump_sql_gz
from utils.db_safety import safe_commit
from utils.tenant_query import TenantContextError, get_tenant_record

logger = logging.getLogger(__name__)


def execute_backup_by_id(backup_id: int) -> Backup:
    """Run pg_dump for an existing Backup record and update its status."""
    try:
        backup = get_tenant_record(Backup, backup_id)
    except TenantContextError:
        raise BackupAutomationError(f'Backup record {backup_id} not found')

    backup.backup_status = BackupStatus.IN_PROGRESS
    backup.started_at = backup.started_at or datetime.now(UTC)
    safe_commit(db.session, error_message='Failed to mark backup in_progress', reraise=True)

    try:
        size = run_pg_dump_sql_gz(backup.backup_path)
        backup.backup_size = size
        backup.backup_status = BackupStatus.COMPLETED
        backup.completed_at = datetime.now(UTC)
        cloud_uri = BackupAutomationService.upload_to_cloud(backup.backup_path)
        if cloud_uri:
            backup.backup_notes = f'cloud_uri={cloud_uri}'
        safe_commit(db.session, error_message='Failed to finalise backup', reraise=True)
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
        safe_commit(db.session, error_message='Failed to save backup failure status')
        logger.error('Backup failed id=%s: %s', backup.id, exc)
        raise BackupAutomationError(str(exc)) from exc
