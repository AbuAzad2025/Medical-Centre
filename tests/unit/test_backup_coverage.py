"""Coverage tests for models/backup.py"""

from datetime import datetime, UTC
from models.backup import Backup, BackupLog


class TestBackup:
    def test_repr(self):
        b = Backup(
            tenant_id=1,
            backup_name='backup_001',
            backup_type='full',
            backup_size=1000,
            backup_path='/backups/backup_001.sql',
            backup_status='COMPLETED',
        )
        assert repr(b) is not None

    def test_get_size_display(self):
        b = Backup(
            tenant_id=1,
            backup_name='backup_001',
            backup_type='full',
            backup_size=1000,
            backup_path='/backups/backup_001.sql',
            backup_status='COMPLETED',
        )
        display = b.get_size_display()
        assert isinstance(display, str)

    def test_get_status_display(self):
        b = Backup(
            tenant_id=1,
            backup_name='backup_001',
            backup_type='full',
            backup_size=1000,
            backup_path='/backups/backup_001.sql',
            backup_status='COMPLETED',
        )
        display = b.get_status_display()
        assert isinstance(display, str)

    def test_get_type_display(self):
        b = Backup(
            tenant_id=1,
            backup_name='backup_001',
            backup_type='full',
            backup_size=1000,
            backup_path='/backups/backup_001.sql',
            backup_status='COMPLETED',
        )
        display = b.get_type_display()
        assert isinstance(display, str)

    def test_is_restorable(self):
        b = Backup(
            tenant_id=1,
            backup_name='backup_001',
            backup_type='full',
            backup_size=1000,
            backup_path='/backups/backup_001.sql',
            backup_status='COMPLETED',
        )
        result = b.is_restorable()
        assert result

    def test_get_duration(self):
        b = Backup(
            tenant_id=1,
            backup_name='backup_001',
            backup_type='full',
            backup_size=1000,
            backup_path='/backups/backup_001.sql',
            backup_status='COMPLETED',
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        result = b.get_duration()
        assert result is not None

    def test_get_duration_display(self):
        b = Backup(
            tenant_id=1,
            backup_name='backup_001',
            backup_type='full',
            backup_size=1000,
            backup_path='/backups/backup_001.sql',
            backup_status='COMPLETED',
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        display = b.get_duration_display()
        assert isinstance(display, str)


class TestBackupLog:
    def test_repr(self):
        bl = BackupLog(
            tenant_id=1,
            backup_id=1,
            log_type='info',
            message='Backup created',
        )
        assert repr(bl) is not None

    def test_get_type_display(self):
        bl = BackupLog(
            tenant_id=1,
            backup_id=1,
            log_type='info',
            message='Backup created',
        )
        display = bl.get_type_display()
        assert isinstance(display, str)
