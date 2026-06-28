#!/usr/bin/env python3
"""Verify Alembic upgrade on a fresh PostgreSQL database (CI + local)."""
from __future__ import annotations

import os
import subprocess
import sys

from sqlalchemy import create_engine, text

ALEMBIC_HEAD_REVISION = 's1_002_tenant_rls_policies'


def main() -> int:
    db_url = os.environ.get('MIGRATE_DATABASE_URL') or os.environ.get('DATABASE_URL')
    if not db_url:
        print('MIGRATE_DATABASE_URL or DATABASE_URL required', file=sys.stderr)
        return 1

    admin_url = os.environ.get('MIGRATE_ADMIN_URL')
    db_name = db_url.rsplit('/', 1)[-1]
    if not admin_url:
        base, _ = db_url.rsplit('/', 1)
        admin_url = f'{base}/postgres'

    print(f'Recreating database {db_name!r}...')
    engine = create_engine(admin_url, isolation_level='AUTOCOMMIT')
    with engine.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}"'))
        conn.execute(text(f'CREATE DATABASE "{db_name}"'))

    env = os.environ.copy()
    env.setdefault('SECRET_KEY', 'migrate-test-secret')
    env.setdefault('FLASK_ENV', 'testing')
    env.setdefault('FLASK_APP', 'wsgi:app')
    env['DATABASE_URL'] = db_url

    print('Running flask db upgrade...')
    result = subprocess.run(
        [sys.executable, '-m', 'flask', 'db', 'upgrade'],
        env=env,
        check=False,
    )
    if result.returncode != 0:
        return result.returncode

    print('Checking alembic head...')
    current = subprocess.run(
        [sys.executable, '-m', 'flask', 'db', 'current'],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    out = (current.stdout or '') + (current.stderr or '')
    if ALEMBIC_HEAD_REVISION not in out and '(head)' not in out:
        print('Unexpected migration head:', out, file=sys.stderr)
        return 1

    print('Migration upgrade OK')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
