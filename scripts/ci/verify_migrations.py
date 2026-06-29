#!/usr/bin/env python3
"""Verify Alembic upgrade on a fresh PostgreSQL database (CI + local)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

# Keep in sync with migrations/versions/ head revision.
ALEMBIC_HEAD_REVISION = 's1_006_rls_phase3'


def _collect_orm_tables() -> set[str]:
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    tables: set[str] = set()
    for base in (root / 'models', root / 'app'):
        if not base.is_dir():
            continue
        for p in base.rglob('*.py'):
            text_body = p.read_text(encoding='utf-8', errors='ignore')
            tables.update(re.findall(r"__tablename__\s*=\s*['\"]([^'\"]+)['\"]", text_body))
    return tables


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
    if ALEMBIC_HEAD_REVISION not in out:
        print('Unexpected migration head (expected', ALEMBIC_HEAD_REVISION, '):', out, file=sys.stderr)
        return 1

    print('Checking ORM tables exist after upgrade...')
    orm_tables = _collect_orm_tables()
    db_engine = create_engine(db_url)
    with db_engine.connect() as conn:
        db_tables = set(inspect(conn).get_table_names())
    # Alembic version table is not an ORM model
    db_tables.discard('alembic_version')
    missing = sorted(orm_tables - db_tables)
    if missing:
        print('Tables expected by ORM but missing after upgrade:', file=sys.stderr)
        for name in missing:
            print(f'  - {name}', file=sys.stderr)
        return 1

    parity = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent / 'check_schema_parity.py')],
        check=False,
    )
    if parity.returncode != 0:
        return parity.returncode

    print(f'Migration upgrade OK ({len(orm_tables)} ORM tables present)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
