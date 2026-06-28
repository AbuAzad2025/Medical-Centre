"""Celery backup task queue tests."""

from unittest.mock import patch

import pytest

from app.extensions import db
from app.shared.enums import BackupStatus
from models.backup import Backup
from services.backup_queue_service import BackupQueueError, queue_system_backup
from services.pg_backup_service import build_backup_path


@pytest.fixture
def celery_eager(monkeypatch):
    monkeypatch.setenv('CELERY_ENABLED', 'true')
    monkeypatch.setenv('CELERY_TASK_ALWAYS_EAGER', 'true')
    from celery_app import get_celery_app
    get_celery_app().conf.task_always_eager = True


class TestCeleryBackupTask:
    def test_queue_system_backup_requires_celery(self, app, monkeypatch):
        monkeypatch.delenv('CELERY_ENABLED', raising=False)
        monkeypatch.delenv('CELERY_TASK_ALWAYS_EAGER', raising=False)
        with pytest.raises(BackupQueueError):
            queue_system_backup(1)

    def test_run_system_backup_executes_pg_dump(self, app, test_user, celery_eager, monkeypatch, tmp_path):
        from celery_app import init_celery_app
        init_celery_app(app)
        monkeypatch.setenv('DATABASE_URL', 'postgresql://u:p@localhost:5432/medical')
        monkeypatch.setenv('BACKUP_LOCAL_DIR', str(tmp_path))
        path = build_backup_path(str(tmp_path), 'celery_test')
        backup = Backup(
            backup_name='celery_test',
            backup_type='full',
            backup_path=path,
            backup_status=BackupStatus.IN_PROGRESS,
            created_by=test_user.id,
        )
        db.session.add(backup)
        db.session.commit()

        with patch('services.backup_execution_service.run_pg_dump_sql_gz', return_value=128), \
             patch('services.backup_execution_service.BackupAutomationService.upload_to_cloud', return_value=None):
            task_id = queue_system_backup(backup.id)

        assert task_id
        db.session.refresh(backup)
        assert backup.backup_status == BackupStatus.COMPLETED
        assert backup.backup_size == 128
