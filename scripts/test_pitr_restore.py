"""
Automated PITR/Restore drill - dump -> restore -> integrity checks -> cleanup.

Usage:
    python scripts/test_pitr_restore.py
    python scripts/test_pitr_restore.py --backup-file backups/path/file.dump
    python scripts/test_pitr_restore.py --keep-restore

Exit code 0 = drill passed, 1 = failed.
NOTE: ASCII-only output for Windows console safety.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlparse

sys.path.insert(0, str(Path(__file__).parent.parent))


MIN_BACKUP_BYTES = 1024
CRITICAL_TABLES = ['users', 'patients', 'visits', 'audit_trails']
RESTORE_DB_SUFFIX = '_restore_drill'


def _parsed():
    return urlparse(os.environ.get('DATABASE_URL', ''))


def _conn_kwargs(dbname=None):
    p = _parsed()
    return {
        'host': p.hostname or 'localhost',
        'port': str(p.port or 5432),
        'user': unquote(p.username or 'postgres'),
        'password': unquote(p.password or ''),
        'dbname': dbname or (p.path or '/').lstrip('/'),
    }


def _env_with_password():
    env = os.environ.copy()
    kw = _conn_kwargs()
    if kw['password']:
        env['PGPASSWORD'] = kw['password']
    return env


def _admin_dbname() -> str:
    return 'postgres'


def _target_dbname() -> str:
    return _conn_kwargs()['dbname'] + RESTORE_DB_SUFFIX


def _drop_target():
    kw = _conn_kwargs(_admin_dbname())
    subprocess.run(
        [
            'dropdb',
            '--if-exists',
            '-h',
            kw['host'],
            '-p',
            kw['port'],
            '-U',
            kw['user'],
            _target_dbname(),
        ],
        capture_output=True,
        env=_env_with_password(),
    )


def run_dump(out_path: str):
    print('[1/5] pg_dump (custom format) ...')
    cmd = [
        'pg_dump',
        '-Fc',
        '--no-owner',
        '--no-privileges',
        '-f',
        out_path,
        os.environ['DATABASE_URL'],
    ]
    proc = subprocess.run(
        cmd, capture_output=True, text=True, env=_env_with_password(), timeout=1800
    )
    if proc.returncode != 0:
        print(f'FAIL pg_dump rc={proc.returncode}: {(proc.stderr or "")[:500]}')
        return False
    size = os.path.getsize(out_path)
    if size < MIN_BACKUP_BYTES:
        print(f'FAIL backup too small: {size}B')
        return False
    print(f'      OK - {size / 1024:.1f} KB')
    return True


def run_restore(backup_path: str) -> tuple[bool, list[str]]:
    """Restore into scratch DB. Returns (ok, error_lines)."""
    target = _target_dbname()
    _drop_target()
    kw = _conn_kwargs(_admin_dbname())

    print(f'[2/5] createdb {target} ...')
    proc = subprocess.run(
        ['createdb', '-h', kw['host'], '-p', kw['port'], '-U', kw['user'], target],
        capture_output=True,
        text=True,
        env=_env_with_password(),
    )
    if proc.returncode != 0:
        print(f'FAIL createdb: {(proc.stderr or "")[:300]}')
        return False, ['createdb failed']

    print(f'[3/5] pg_restore into {target} ...')
    proc = subprocess.run(
        [
            'pg_restore',
            '--no-owner',
            '--no-privileges',
            '-h',
            kw['host'],
            '-p',
            kw['port'],
            '-U',
            kw['user'],
            '-d',
            target,
            backup_path,
        ],
        capture_output=True,
        text=True,
        env=_env_with_password(),
        timeout=1800,
    )
    err_lines = [ln for ln in (proc.stderr or '').splitlines() if ln.strip()]
    # pg_restore exits nonzero if ANY error occurred; collect them.
    real_errors = [
        ln for ln in err_lines if 'error' in ln.lower() and 'already exists' not in ln.lower()
    ]
    print(f'      pg_restore rc={proc.returncode}, {len(real_errors)} error line(s)')
    if real_errors[:10]:
        for ln in real_errors[:10]:
            print(f'        ! {ln[:160]}')
    return proc.returncode == 0 and not real_errors, real_errors


def verify_integrity():
    """Critical tables exist in restore target; row counts vs SOURCE via psycopg2."""
    print('[4/5] integrity checks ...')
    failures = []

    import psycopg2

    src_kw = _conn_kwargs()

    def _count(conn, table):
        cur = conn.cursor()
        cur.execute(
            'SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = %s)',
            (table,),
        )
        exists = cur.fetchone()[0]
        if not exists:
            return None
        cur.execute(f'SELECT COUNT(*) FROM "{table}"')  # noqa: S608
        n = cur.fetchone()[0]
        cur.close()
        return n

    conn_src = psycopg2.connect(connect_timeout=10, **src_kw)
    conn_dst = psycopg2.connect(connect_timeout=10, **_conn_kwargs(_target_dbname()))
    try:
        for table in CRITICAL_TABLES:
            n_src = _count(conn_src, table)
            n_dst = _count(conn_dst, table)
            if n_src is None:
                failures.append(f'SOURCE missing table {table}')
                continue
            if n_dst is None:
                failures.append(f'RESTORED missing table {table}')
                continue
            status = 'OK' if n_dst == n_src else f'DIFF src={n_src} dst={n_dst}'
            print(f'      {table}: {status}')
            if n_dst != n_src:
                failures.append(f'{table}: row count differs ({n_src} -> {n_dst})')
    finally:
        conn_src.close()
        conn_dst.close()

    if failures:
        print('      FAIL:')
        for f_ in failures:
            print(f'        - {f_}')
        return False, failures
    print('      PASS - critical tables match source row-for-row')
    return True, []


def cleanup(keep: bool):
    print('[5/5] cleanup ...')
    if keep:
        print(f'      kept {_target_dbname()} (--keep-restore)')
        return
    _drop_target()
    print('      OK - scratch DB dropped')


def main() -> int:
    parser = argparse.ArgumentParser(description='Automated DR restore drill')
    parser.add_argument('--backup-file', help='existing .dump file instead of fresh pg_dump')
    parser.add_argument('--keep-restore', action='store_true')
    args = parser.parse_args()

    url = os.environ.get('DATABASE_URL', '')
    if not url:
        print('ERROR: DATABASE_URL required')
        return 1
    if url.startswith('sqlite'):
        print('SKIP: sqlite unsupported (PostgreSQL-only)')
        return 0

    tmp_dir = None
    try:
        if args.backup_file:
            backup_path = args.backup_file
            if not os.path.exists(backup_path):
                print(f'ERROR: not found: {backup_path}')
                return 1
            print(f'[0/5] using existing backup: {backup_path}')
        else:
            tmp_dir = tempfile.mkdtemp(prefix='drill_')
            backup_path = os.path.join(tmp_dir, 'drill_backup.dump')
            if not run_dump(backup_path):
                return 1

        ok_restore, errs = run_restore(backup_path)
        ok_integrity, _fails = verify_integrity()
        cleanup(args.keep_restore)

        print('=' * 50)
        if ok_restore and ok_integrity:
            print('DR DRILL PASSED')
            return 0
        if not ok_restore:
            print('DR DRILL FAILED (restore errors):')
            for e in errs[:20]:
                print(f'  ! {e[:200]}')
        else:
            print('DR DRILL FAILED (integrity mismatch)')
        return 1
    finally:
        if tmp_dir and Path(tmp_dir).is_dir():
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())
