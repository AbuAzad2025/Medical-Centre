"""Automated backup scheduler and cloud upload tests."""

import os
from unittest.mock import MagicMock, patch

import pytest

from app.shared.enums import BackupStatus
from models.backup import Backup
from services.backup_automation_service import BackupAutomationError, BackupAutomationService


class TestBackupAutomationService:
    def test_run_scheduled_backup_persists_completed_record(self, app, test_user, monkeypatch):
        monkeypatch.setenv('DATABASE_URL', 'postgresql://u:p@localhost:5432/medical')
        with patch('services.backup_automation_service.run_pg_dump_sql_gz', return_value=128), \
             patch.object(BackupAutomationService, 'upload_to_cloud', return_value=None):
            record = BackupAutomationService.run_scheduled_backup(created_by=test_user.id)
        assert record.backup_status == BackupStatus.COMPLETED
        assert record.backup_size == 128
        saved = Backup.query.get(record.id)
        assert saved is not None

    def test_upload_to_cloud_requires_bucket(self, app, tmp_path, monkeypatch):
        file_path = tmp_path / 'backup.sql.gz'
        file_path.write_bytes(b'x')
        assert BackupAutomationService.upload_to_cloud(str(file_path)) is None

    def test_upload_to_cloud_uses_boto3(self, app, tmp_path, monkeypatch):
        monkeypatch.setenv('BACKUP_S3_BUCKET', 'medical-backups')
        file_path = tmp_path / 'backup.sql.gz'
        file_path.write_bytes(b'gzip-data')
        mock_client = MagicMock()
        with patch('boto3.client', return_value=mock_client):
            uri = BackupAutomationService.upload_to_cloud(str(file_path))
        assert uri == 's3://medical-backups/medical-system/backups/backup.sql.gz'
        mock_client.upload_file.assert_called_once()

    def test_tick_skips_when_disabled(self, app, monkeypatch):
        monkeypatch.delenv('BACKUP_AUTOMATION_ENABLED', raising=False)
        with patch.object(BackupAutomationService, 'run_scheduled_backup') as run:
            BackupAutomationService.tick(app)
        run.assert_not_called()
