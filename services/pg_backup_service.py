"""Native PostgreSQL backup/restore via pg_dump and psql (production pilot)."""
from __future__ import annotations

import gzip
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import unquote, urlparse

logger = logging.getLogger(__name__)


class PgBackupError(RuntimeError):
    """Raised when pg_dump/psql backup operations fail."""


@dataclass(frozen=True)
class PgConnectionParams:
    host: str
    port: str
    user: str
    password: str
    database: str


def _resolve_database_url(database_url: Optional[str] = None) -> str:
    url = (
        database_url
        or os.environ.get('DATABASE_URL')
        or os.environ.get('SQLALCHEMY_DATABASE_URI')
    )
    if not url:
        raise PgBackupError(
            'DATABASE_URL or SQLALCHEMY_DATABASE_URI is required for PostgreSQL backup'
        )
    if url.startswith('sqlite'):
        raise PgBackupError('SQLite databases must use file-level backup; pg_dump is PostgreSQL-only')
    return url


def parse_database_url(database_url: str) -> PgConnectionParams:
    parsed = urlparse(database_url)
    if parsed.scheme not in ('postgresql', 'postgres'):
        raise PgBackupError(f'Unsupported database scheme: {parsed.scheme!r}')
    database = (parsed.path or '').lstrip('/')
    if not database:
        raise PgBackupError('Database name missing from connection URL')
    return PgConnectionParams(
        host=parsed.hostname or 'localhost',
        port=str(parsed.port or 5432),
        user=unquote(parsed.username or 'postgres'),
        password=unquote(parsed.password or ''),
        database=database,
    )


def _find_executable(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise PgBackupError(f'{name} not found on PATH — install PostgreSQL client tools')
    return path


def _pg_env(params: PgConnectionParams) -> dict[str, str]:
    env = os.environ.copy()
    if params.password:
        env['PGPASSWORD'] = params.password
    return env


def build_backup_path(base_dir: str, backup_name: str, when: Optional[datetime] = None) -> str:
    ts = (when or datetime.now(timezone.utc)).strftime('%Y%m%d_%H%M%S')
    folder = os.path.join(base_dir, ts[:4], ts[4:6])
    os.makedirs(folder, exist_ok=True)
    safe_name = ''.join(c if c.isalnum() or c in ('-', '_') else '_' for c in backup_name)
    return os.path.join(folder, f'{safe_name}_{ts}.sql.gz')


def run_pg_dump_sql_gz(output_path: str, database_url: Optional[str] = None) -> int:
    """Execute pg_dump and write a compressed plain-SQL artifact (.sql.gz)."""
    params = parse_database_url(_resolve_database_url(database_url))
    pg_dump = _find_executable('pg_dump')
    os.makedirs(os.path.dirname(os.path.abspath(output_path)) or '.', exist_ok=True)

    cmd = [
        pg_dump,
        '--host', params.host,
        '--port', params.port,
        '--username', params.user,
        '--dbname', params.database,
        '--format', 'plain',
        '--no-owner',
        '--no-acl',
        '--encoding', 'UTF8',
    ]
    logger.info(
        'Starting pg_dump host=%s port=%s db=%s -> %s',
        params.host, params.port, params.database, output_path,
    )
    proc = subprocess.run(
        cmd,
        env=_pg_env(params),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        err = proc.stderr.decode('utf-8', errors='replace').strip()
        logger.error('pg_dump failed (exit %s): %s', proc.returncode, err)
        raise PgBackupError(err or f'pg_dump exited with code {proc.returncode}')

    with gzip.open(output_path, 'wb', compresslevel=6) as gz:
        gz.write(proc.stdout)

    size = os.path.getsize(output_path)
    if size <= 0:
        raise PgBackupError('Backup artifact is empty')
    logger.info('pg_dump backup completed: %s (%s bytes)', output_path, size)
    return size


def restore_pg_sql_gz(backup_path: str, database_url: Optional[str] = None) -> None:
    """Restore a .sql.gz pg_dump plain-SQL backup via psql."""
    if not os.path.isfile(backup_path):
        raise PgBackupError(f'Backup file not found: {backup_path}')
    if not backup_path.endswith('.sql.gz'):
        raise PgBackupError('PostgreSQL restore requires a .sql.gz pg_dump artifact')

    params = parse_database_url(_resolve_database_url(database_url))
    psql = _find_executable('psql')

    with gzip.open(backup_path, 'rb') as gz:
        sql_bytes = gz.read()
    if not sql_bytes.strip():
        raise PgBackupError('Backup SQL payload is empty')

    cmd = [
        psql,
        '--host', params.host,
        '--port', params.port,
        '--username', params.user,
        '--dbname', params.database,
        '--single-transaction',
        '--set', 'ON_ERROR_STOP=1',
        '--quiet',
    ]
    logger.info(
        'Starting psql restore host=%s port=%s db=%s <- %s',
        params.host, params.port, params.database, backup_path,
    )
    proc = subprocess.run(
        cmd,
        env=_pg_env(params),
        input=sql_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        err = proc.stderr.decode('utf-8', errors='replace').strip()
        logger.error('psql restore failed (exit %s): %s', proc.returncode, err)
        raise PgBackupError(err or f'psql exited with code {proc.returncode}')
    logger.info('psql restore completed for %s', backup_path)
