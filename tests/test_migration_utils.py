"""Migration helper smoke tests (no DB required)."""

from migrations.migration_utils import (
    column_exists,
    index_exists,
    table_exists,
)


def test_migration_utils_importable():
    assert callable(table_exists)
    assert callable(column_exists)
    assert callable(index_exists)
