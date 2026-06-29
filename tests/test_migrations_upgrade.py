"""Migration chain smoke tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from migrations.migration_utils import column_exists, fk_exists, index_exists, table_exists

# Keep in sync with the latest Alembic revision in migrations/versions/.
ALEMBIC_HEAD_REVISION = 's1_004_expenses_rls_uniques'


def test_migration_utils_callable():
    assert callable(table_exists)
    assert callable(column_exists)
    assert callable(index_exists)
    assert callable(fk_exists)


def test_verify_migrations_script_exists():
    script = Path(__file__).parent.parent / 'scripts' / 'verify_migrations.py'
    assert script.is_file()


def test_check_schema_parity_script():
    script = Path(__file__).parent.parent / 'scripts' / 'check_schema_parity.py'
    assert script.is_file()
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_alembic_single_head(app):
    """Revision graph must resolve to one head (no branches)."""
    result = subprocess.run(
        [sys.executable, '-m', 'flask', 'db', 'heads'],
        env={
            **__import__('os').environ,
            'SECRET_KEY': 'test',
            'FLASK_ENV': 'testing',
            'FLASK_APP': 'wsgi:app',
            'DATABASE_URL': 'postgresql://localhost/test',
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    head_lines = [
        ln.strip() for ln in result.stdout.splitlines()
        if ln.strip() and ('(head)' in ln or ALEMBIC_HEAD_REVISION in ln)
    ]
    assert len(head_lines) == 1
    assert ALEMBIC_HEAD_REVISION in head_lines[0]
