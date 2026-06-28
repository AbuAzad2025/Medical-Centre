"""PostgreSQL pg_dump backup service tests (mocked subprocess)."""

import gzip
import io
import os
from unittest.mock import MagicMock, patch

import pytest

from services.pg_backup_service import (
    BACKUP_CHUNK_SIZE,
    PgBackupError,
    build_backup_path,
    parse_database_url,
    restore_pg_sql_gz,
    run_pg_dump_sql_gz,
)


class TestParseDatabaseUrl:
    def test_parses_postgresql_url(self):
        params = parse_database_url('postgresql://dbuser:secret%40x@dbhost:5433/medical_db')
        assert params.host == 'dbhost'
        assert params.port == '5433'
        assert params.user == 'dbuser'
        assert params.password == 'secret@x'
        assert params.database == 'medical_db'

    def test_rejects_sqlite(self):
        with pytest.raises(PgBackupError, match='SQLite'):
            run_pg_dump_sql_gz('/tmp/x.sql.gz', database_url='sqlite:///:memory:')


class TestPgDumpExecution:
    def test_run_pg_dump_streams_gzip_artifact(self, tmp_path, monkeypatch):
        monkeypatch.setenv(
            'DATABASE_URL',
            'postgresql://postgres:pass@localhost:5432/medical_system',
        )
        monkeypatch.setenv('BACKUP_TIMEOUT_SECONDS', '60')
        out = str(tmp_path / 'backup.sql.gz')

        sql_data = b'CREATE TABLE patients (id int);'
        fake_proc = MagicMock()
        fake_proc.stdout = io.BytesIO(sql_data)
        fake_proc.stderr = io.BytesIO(b'')
        fake_proc.returncode = 0
        fake_proc.wait = MagicMock(return_value=0)
        fake_proc.poll = MagicMock(return_value=0)

        with patch('services.pg_backup_service.shutil.which', return_value='/usr/bin/pg_dump'), \
             patch('services.pg_backup_service.subprocess.Popen', return_value=fake_proc) as popen:
            size = run_pg_dump_sql_gz(out)

        assert size > 0
        assert os.path.isfile(out)
        with gzip.open(out, 'rb') as gz:
            assert b'CREATE TABLE' in gz.read()
        popen.assert_called_once()
        cmd = popen.call_args[0][0]
        assert cmd[0] == '/usr/bin/pg_dump'
        assert 'PGPASSWORD' in popen.call_args[1]['env']

    def test_pg_dump_failure_raises(self, tmp_path, monkeypatch):
        monkeypatch.setenv('DATABASE_URL', 'postgresql://u:p@localhost:5432/db')
        monkeypatch.setenv('BACKUP_TIMEOUT_SECONDS', '60')
        out = str(tmp_path / 'fail.sql.gz')

        fake_proc = MagicMock()
        fake_proc.stdout = io.BytesIO(b'')
        fake_proc.stderr = io.BytesIO(b'connection refused')
        fake_proc.returncode = 1
        fake_proc.wait = MagicMock(return_value=1)
        fake_proc.poll = MagicMock(return_value=1)
        fake_proc.stderr.read = MagicMock(return_value=b'connection refused')

        with patch('services.pg_backup_service.shutil.which', return_value='/usr/bin/pg_dump'), \
             patch('services.pg_backup_service.subprocess.Popen', return_value=fake_proc):
            with pytest.raises(PgBackupError, match='connection refused'):
                run_pg_dump_sql_gz(out)

    def test_pg_dump_timeout_raises(self, tmp_path, monkeypatch):
        monkeypatch.setenv('DATABASE_URL', 'postgresql://u:p@localhost:5432/db')
        monkeypatch.setenv('BACKUP_TIMEOUT_SECONDS', '1')
        out = str(tmp_path / 'timeout.sql.gz')

        import subprocess as sp

        fake_proc = MagicMock()
        fake_proc.stdout = io.BytesIO(b'partial data')
        fake_proc.stderr = io.BytesIO(b'')
        call_count = [0]

        def wait_side_effect(timeout=None):
            call_count[0] += 1
            if call_count[0] == 1:
                raise sp.TimeoutExpired('pg_dump', 1)
            return -9

        fake_proc.wait = MagicMock(side_effect=wait_side_effect)
        fake_proc.kill = MagicMock()
        fake_proc.poll = MagicMock(return_value=-9)

        with patch('services.pg_backup_service.shutil.which', return_value='/usr/bin/pg_dump'), \
             patch('services.pg_backup_service.subprocess.Popen', return_value=fake_proc):
            with pytest.raises(PgBackupError, match='timed out'):
                run_pg_dump_sql_gz(out)
        fake_proc.kill.assert_called()


class TestPgRestoreExecution:
    def test_restore_invokes_psql_with_decompressed_sql(self, tmp_path, monkeypatch):
        monkeypatch.setenv('DATABASE_URL', 'postgresql://u:p@localhost:5432/db')
        path = tmp_path / 'restore.sql.gz'
        with gzip.open(path, 'wb') as gz:
            gz.write(b'SELECT 1;')

        fake_proc = MagicMock()
        fake_proc.returncode = 0
        fake_proc.stdout = b''
        fake_proc.stderr = b''

        with patch('services.pg_backup_service.shutil.which', return_value='/usr/bin/psql'), \
             patch('services.pg_backup_service.subprocess.run', return_value=fake_proc) as run:
            restore_pg_sql_gz(str(path))

        run.assert_called_once()
        assert run.call_args[1]['input'] == b'SELECT 1;'


class TestBuildBackupPath:
    def test_builds_sql_gz_under_dated_folder(self, tmp_path):
        path = build_backup_path(str(tmp_path), 'pilot_backup')
        assert path.endswith('.sql.gz')
        assert 'pilot_backup' in os.path.basename(path)
