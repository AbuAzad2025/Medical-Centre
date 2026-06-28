"""PostgreSQL pg_dump backup service tests (mocked subprocess)."""

import gzip
import os
from unittest.mock import MagicMock, patch

import pytest

from services.pg_backup_service import (
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
    def test_run_pg_dump_writes_gzip_artifact(self, tmp_path, monkeypatch):
        monkeypatch.setenv(
            'DATABASE_URL',
            'postgresql://postgres:pass@localhost:5432/medical_system',
        )
        out = str(tmp_path / 'backup.sql.gz')

        fake_proc = MagicMock()
        fake_proc.returncode = 0
        fake_proc.stdout = b'CREATE TABLE patients (id int);'
        fake_proc.stderr = b''

        with patch('services.pg_backup_service.shutil.which', return_value='/usr/bin/pg_dump'), \
             patch('services.pg_backup_service.subprocess.run', return_value=fake_proc) as run:
            size = run_pg_dump_sql_gz(out)

        assert size > 0
        assert os.path.isfile(out)
        with gzip.open(out, 'rb') as gz:
            assert b'CREATE TABLE' in gz.read()
        run.assert_called_once()
        cmd = run.call_args[0][0]
        assert cmd[0] == '/usr/bin/pg_dump'
        assert 'PGPASSWORD' in run.call_args[1]['env']

    def test_pg_dump_failure_raises(self, tmp_path, monkeypatch):
        monkeypatch.setenv('DATABASE_URL', 'postgresql://u:p@localhost:5432/db')
        out = str(tmp_path / 'fail.sql.gz')
        fake_proc = MagicMock()
        fake_proc.returncode = 1
        fake_proc.stdout = b''
        fake_proc.stderr = b'connection refused'

        with patch('services.pg_backup_service.shutil.which', return_value='/usr/bin/pg_dump'), \
             patch('services.pg_backup_service.subprocess.run', return_value=fake_proc):
            with pytest.raises(PgBackupError, match='connection refused'):
                run_pg_dump_sql_gz(out)


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
