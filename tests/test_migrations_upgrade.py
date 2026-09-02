"""Migration chain smoke tests."""

from __future__ import annotations

import subprocess
import sys

from migrations.migration_utils import column_exists, fk_exists, index_exists, table_exists

# Expected heads in the migration graph.
# The migration chain continues from s2_011_clean_schema through s3_* migrations.
EXPECTED_HEADS = {
    'f224b8d0c4d2',
}


def test_migration_utils_callable():
    assert callable(table_exists)
    assert callable(column_exists)
    assert callable(index_exists)
    assert callable(fk_exists)
    from migrations.migration_utils import disable_tenant_rls, enable_tenant_rls

    assert callable(enable_tenant_rls)
    assert callable(disable_tenant_rls)


def test_alembic_heads_expected(app):
    """Revision graph must resolve to expected heads (multiple independent chains)."""
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
    head_revisions = set()
    for ln in result.stdout.splitlines():
        ln = ln.strip()
        if ln.strip() and '(head)' in ln:
            rev = ln.split(' ')[0].strip()
            if rev:
                head_revisions.add(rev)

    # Verify all expected heads are present
    missing = EXPECTED_HEADS - head_revisions
    assert not missing, f'Missing expected heads: {missing}. Found: {head_revisions}'

    # Verify no unexpected heads (allow some flexibility for future additions)
    unexpected = head_revisions - EXPECTED_HEADS
    assert not unexpected, f'Unexpected heads found: {unexpected}. Expected: {EXPECTED_HEADS}'
