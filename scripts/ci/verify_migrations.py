#!/usr/bin/env python3
"""Create a fresh DB, run all Alembic migrations, verify success."""

from __future__ import annotations

import os
import subprocess
import sys

import sqlalchemy as sa

ADMIN_URL = os.environ['MIGRATE_ADMIN_URL']
TARGET_URL = os.environ['MIGRATE_DATABASE_URL']
ALEMBIC_HEAD = 'p5_004_add_controlled_schedule_to_medication'


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    print(f'  running: {" ".join(cmd)}', flush=True)
    return subprocess.run(cmd, capture_output=True, text=True, check=False, **kwargs)


def main() -> int:
    _admin = sa.create_engine(ADMIN_URL, isolation_level='AUTOCOMMIT')
    db_name = TARGET_URL.rsplit('/', 1)[-1]

    # Drop if leftover from previous run, then create fresh
    with _admin.connect() as c:
        c.execute(sa.text(f'DROP DATABASE IF EXISTS "{db_name}"'))
        c.execute(sa.text(f'CREATE DATABASE "{db_name}" OWNER postgres'))
    _admin.dispose()
    print(f'OK  created database "{db_name}"')

    # Run migrations via Flask-Migrate CLI
    env = {
        **os.environ,
        'DATABASE_URL': TARGET_URL,
        'RLS_BYPASS_ALLOWED': '1',
        'FLASK_APP': 'wsgi:app',
        'FLASK_ENV': 'testing',
        'APP_ENV': 'testing',
        'SECRET_KEY': os.environ.get('SECRET_KEY', 'ci'),
    }
    result = _run([sys.executable, '-m', 'flask', 'db', 'upgrade', 'heads'], env=env)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        print('FAIL flask db upgrade')
        return 1
    print('OK  flask db upgrade succeeded')

    # Verify all expected heads are present
    result = _run([sys.executable, '-m', 'flask', 'db', 'heads'], env=env)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        print('FAIL flask db heads')
        return 1
    
    # Extract all head revisions from output
    head_revisions = []
    for ln in result.stdout.splitlines():
        ln = ln.strip()
        if ln and ' (head)' in ln:
            head_rev = ln.split(' -> ')[0].split(' ')[0].strip()
            if head_rev:
                head_revisions.append(head_rev)
    
    print(f'OK  head revisions: {", ".join(head_revisions)}')
    
    # Verify p5_004 is among the heads
    if ALEMBIC_HEAD not in head_revisions:
        print(f'FAIL expected head {ALEMBIC_HEAD} not found in heads: {head_revisions}')
        return 1
    print(f'OK  expected head {ALEMBIC_HEAD} present')
    
    # Verify alembic_version has one of the heads
    _target = sa.create_engine(TARGET_URL)
    with _target.connect() as c:
        row = c.execute(sa.text('SELECT version_num FROM alembic_version')).fetchone()
        assert row is not None, 'alembic_version is empty'
        assert row[0] in head_revisions, f'{row[0]} not in heads: {head_revisions}'
    _target.dispose()
    print(f'OK  alembic_version confirms applied head: {row[0]}')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
